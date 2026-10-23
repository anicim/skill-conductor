#!/usr/bin/env python3
"""Run trigger evaluation for a skill description with Codex."""

import argparse
import json
import queue
import re
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

try:
    from .utils import codex_command, codex_environment, parse_skill_md
except ImportError:
    from utils import codex_command, codex_environment, parse_skill_md


AttemptStatus = Literal[
    "triggered", "not_triggered", "blocked", "timeout", "cli_error", "unexpected_tool_call"
]


@dataclass(frozen=True)
class TriggerAttempt:
    status: AttemptStatus
    evidence: str | None = None
    detail: str | None = None


_READ_COMMAND = re.compile(
    r"^\s*(?:(?:pwsh|powershell(?:\.exe)?)\b.*?\s-(?:command|c)\s+[\"']?\s*"
    r"|cmd(?:\.exe)?\s+/(?:c|k)\s+[\"']?\s*"
    r"|(?:bash|sh|zsh)\b.*?\s-[a-z]*c\s+[\"']?\s*)?"
    r"(?:get-content|cat|type|more|head|tail|less)\b",
    re.IGNORECASE,
)
_BLOCK_MARKERS = (
    "blocked by", "denied by", "not allowed by", "approval denied",
    "approval was rejected", "policy denied", "sandbox denied", "requires approval",
    "permission denied",
)


def _event_text(event: dict) -> str:
    return json.dumps(event, ensure_ascii=False).casefold()


def _is_blocked(event: dict) -> bool:
    text = _event_text(event)
    return any(marker in text for marker in _BLOCK_MARKERS)


def classify_trigger_events(events: list[dict], skill_path: Path) -> TriggerAttempt:
    """Classify JSONL events; only a successful completed read proves activation."""
    expected_path = str(skill_path).replace("/", "\\").casefold()
    for event in events:
        event_type = event.get("type")
        item = event.get("item") or {}
        if event_type in {"item.started", "item.updated", "item.completed"}:
            if item.get("type") == "mcp_tool_call":
                return TriggerAttempt("unexpected_tool_call", detail="Codex emitted an MCP tool call before reading the test skill.")
            if event_type != "item.completed" or item.get("type") != "command_execution":
                continue
            command = item.get("command", "")
            normalized_command = command.replace("/", "\\").casefold()
            if expected_path not in normalized_command or not _READ_COMMAND.search(command):
                continue
            if _is_blocked(event):
                return TriggerAttempt("blocked", evidence=command, detail="The read was blocked by policy or approval.")
            if item.get("status") == "completed" and item.get("exit_code") == 0:
                return TriggerAttempt("triggered", evidence=command)
        elif event_type in {"error", "turn.failed"}:
            status: AttemptStatus = "blocked" if _is_blocked(event) else "cli_error"
            return TriggerAttempt(status, detail=event.get("message") or event.get("error") or event_type)
    return TriggerAttempt("not_triggered")


def _stop_process(process: subprocess.Popen) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def _read_stdout(stream, output: queue.Queue[str | None]) -> None:
    for line in stream:
        output.put(line)
    output.put(None)


def run_single_query(
    query: str,
    skill_name: str,
    skill_description: str,
    timeout: int,
    model: str | None = None,
) -> TriggerAttempt:
    """Run one isolated query and stop when its outcome is known."""
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", skill_name) or len(skill_name) > 64:
        raise ValueError(f"Invalid skill name: {skill_name!r}")

    with tempfile.TemporaryDirectory(prefix="skill-conductor-eval-") as temp_dir:
        project_root = Path(temp_dir)
        skill_dir = project_root / ".agents" / "skills" / skill_name
        skill_dir.mkdir(parents=True)
        skill_md = (
            f"---\nname: {skill_name}\ndescription: {json.dumps(skill_description, ensure_ascii=False)}\n---\n"
        )
        (skill_dir / "SKILL.md").write_text(skill_md, encoding="utf-8")

        command = codex_command() + [
            "exec", "--json", "--ephemeral", "--ignore-user-config",
            "--skip-git-repo-check", "--approve-for-me",
        ]
        if model:
            command.extend(["--model", model])
        command.append("-")

        try:
            with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as stderr_file:
                process = subprocess.Popen(
                    command,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=stderr_file,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                    cwd=project_root,
                    env=codex_environment(project_root),
                )
                if process.stdin is not None:
                    try:
                        process.stdin.write(query)
                        process.stdin.close()
                    except BrokenPipeError:
                        pass

                output: queue.Queue[str | None] = queue.Queue()
                reader = threading.Thread(target=_read_stdout, args=(process.stdout, output), daemon=True)
                reader.start()
                expected_path = skill_dir / "SKILL.md"
                deadline = time.monotonic() + timeout
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        _stop_process(process)
                        return TriggerAttempt("timeout", detail=f"Codex exceeded {timeout}s timeout.")
                    try:
                        line = output.get(timeout=remaining)
                    except queue.Empty:
                        _stop_process(process)
                        return TriggerAttempt("timeout", detail=f"Codex exceeded {timeout}s timeout.")
                    if line is None:
                        break
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError as error:
                        _stop_process(process)
                        return TriggerAttempt("cli_error", detail=f"Codex emitted invalid JSONL: {error}")
                    attempt = classify_trigger_events([event], expected_path)
                    if attempt.status != "not_triggered":
                        _stop_process(process)
                        return attempt

                try:
                    return_code = process.wait(timeout=max(0.0, deadline - time.monotonic()))
                except subprocess.TimeoutExpired:
                    _stop_process(process)
                    return TriggerAttempt("timeout", detail=f"Codex exceeded {timeout}s timeout.")
                stderr_file.seek(0)
                details = stderr_file.read().strip()[-1000:]
                if return_code:
                    status: AttemptStatus = "blocked" if any(marker in details.casefold() for marker in _BLOCK_MARKERS) else "cli_error"
                    return TriggerAttempt(status, detail=details or f"Codex CLI exited with status {return_code}.")
                return TriggerAttempt("not_triggered")
        except FileNotFoundError as error:
            return TriggerAttempt("cli_error", detail=str(error))


def run_eval(
    eval_set: list[dict],
    skill_name: str,
    description: str,
    num_workers: int,
    timeout: int,
    runs_per_query: int = 1,
    trigger_threshold: float = 0.5,
    model: str | None = None,
) -> dict:
    """Run the full eval set and return results."""
    results = []

    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        future_to_info = {}
        for item in eval_set:
            for run_idx in range(runs_per_query):
                future = executor.submit(
                    run_single_query,
                    item["query"],
                    skill_name,
                    description,
                    timeout,
                    model,
                )
                future_to_info[future] = (item, run_idx)

        query_attempts: dict[str, list[TriggerAttempt]] = {}
        query_items: dict[str, dict] = {}
        for future in as_completed(future_to_info):
            item, _ = future_to_info[future]
            query = item["query"]
            query_items[query] = item
            if query not in query_attempts:
                query_attempts[query] = []
            try:
                query_attempts[query].append(future.result())
            except Exception as e:
                print(f"Warning: query failed: {e}", file=sys.stderr)
                query_attempts[query].append(TriggerAttempt("cli_error", detail=str(e)))

    for query, attempts in query_attempts.items():
        item = query_items[query]
        successful_attempts = all(attempt.status in {"triggered", "not_triggered"} for attempt in attempts)
        triggers = sum(attempt.status == "triggered" for attempt in attempts)
        should_trigger = item["should_trigger"]
        if successful_attempts:
            trigger_rate = triggers / len(attempts)
            did_pass = trigger_rate >= trigger_threshold if should_trigger else trigger_rate < trigger_threshold
            incomplete_reason = None
        else:
            trigger_rate = None
            did_pass = None
            reasons: dict[str, int] = {}
            for attempt in attempts:
                if attempt.status not in {"triggered", "not_triggered"}:
                    reasons[attempt.status] = reasons.get(attempt.status, 0) + 1
            incomplete_reason = ", ".join(f"{count}/{len(attempts)} {status}" for status, count in sorted(reasons.items()))
        result = {
            "query": query,
            "should_trigger": should_trigger,
            "status": "complete" if successful_attempts else "incomplete",
            "trigger_rate": trigger_rate,
            "triggers": triggers,
            "runs": len(attempts),
            "pass": did_pass,
            "attempts": [
                {"status": attempt.status, "evidence": attempt.evidence, "detail": attempt.detail}
                for attempt in attempts
            ],
        }
        if incomplete_reason:
            result["incomplete_reason"] = incomplete_reason
        results.append(result)

    passed = sum(1 for result in results if result["pass"] is True)
    failed = sum(1 for result in results if result["pass"] is False)
    incomplete = sum(1 for result in results if result["status"] == "incomplete")
    total = len(results)

    return {
        "skill_name": skill_name,
        "description": description,
        "results": results,
        "summary": {
            "total": total,
            "passed": passed,
            "failed": failed,
            "incomplete": incomplete,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run trigger evaluation for a skill description")
    parser.add_argument("--eval-set", required=True, help="Path to eval set JSON file")
    parser.add_argument("--skill-path", required=True, help="Path to skill directory")
    parser.add_argument("--description", default=None, help="Override description to test")
    parser.add_argument("--num-workers", type=int, default=1, help="Number of parallel workers")
    parser.add_argument("--timeout", type=int, default=120, help="Timeout per query in seconds")
    parser.add_argument("--runs-per-query", type=int, default=3, help="Number of runs per query")
    parser.add_argument("--trigger-threshold", type=float, default=0.5, help="Trigger rate threshold")
    parser.add_argument("--model", default=None, help="Optional Codex model override")
    parser.add_argument("--verbose", action="store_true", help="Print progress to stderr")
    return parser


def main():
    args = build_parser().parse_args()

    eval_set = json.loads(Path(args.eval_set).read_text())
    skill_path = Path(args.skill_path)

    if not (skill_path / "SKILL.md").exists():
        print(f"Error: No SKILL.md found at {skill_path}", file=sys.stderr)
        sys.exit(1)

    name, original_description, _ = parse_skill_md(skill_path)
    description = args.description or original_description

    if args.verbose:
        print(f"Evaluating: {description}", file=sys.stderr)

    output = run_eval(
        eval_set=eval_set,
        skill_name=name,
        description=description,
        num_workers=args.num_workers,
        timeout=args.timeout,
        runs_per_query=args.runs_per_query,
        trigger_threshold=args.trigger_threshold,
        model=args.model,
    )

    if args.verbose:
        summary = output["summary"]
        print(
            f"Results: {summary['passed']}/{summary['total']} passed; "
            f"{summary.get('incomplete', 0)} incomplete",
            file=sys.stderr,
        )
        for r in output["results"]:
            if r["status"] == "incomplete":
                print(
                    f"  [INCOMPLETE] expected={r['should_trigger']}: "
                    f"{r['query'][:70]} ({r.get('incomplete_reason', 'infrastructure error')})",
                    file=sys.stderr,
                )
                continue
            status = "PASS" if r["pass"] else "FAIL"
            rate_str = f"{r['triggers']}/{r['runs']}"
            print(f"  [{status}] rate={rate_str} expected={r['should_trigger']}: {r['query'][:70]}", file=sys.stderr)

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
