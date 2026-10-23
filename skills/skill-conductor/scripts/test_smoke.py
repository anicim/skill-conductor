#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Smoke tests for skill-conductor scripts.

Run: uv run scripts/test_smoke.py

Tests verify the most critical scripts execute successfully on a known-good
skill, fail loudly on a known-bad skill, and produce expected output shapes.

This is not a full unit test suite — it's a fast safety net so we don't ship
broken scripts. Real behavior is verified by Mode 3 VALIDATE on real skills.
"""

import json
import io
import os
import shutil
import subprocess
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = SKILL_DIR / "scripts"
UV_BIN = shutil.which("uv") or os.path.expanduser("~/.local/bin/uv")
RESULTS = []


def run(label: str, fn) -> None:
    """Run a test, print pass/fail, accumulate failures."""
    try:
        fn()
        RESULTS.append((label, True, None))
        print(f"  ✓ {label}")
    except AssertionError as e:
        RESULTS.append((label, False, str(e)))
        print(f"  ✗ {label}: {e}")
    except Exception as e:
        RESULTS.append((label, False, f"{type(e).__name__}: {e}"))
        print(f"  ✗ {label}: {type(e).__name__}: {e}")


def make_good_skill(tmp: Path) -> Path:
    """Create a minimally valid skill folder for tests."""
    skill = tmp / "test-good-skill"
    skill.mkdir()
    (skill / "SKILL.md").write_text(
        "---\n"
        "name: test-good-skill\n"
        "description: A test skill for smoke testing. Use when running smoke tests.\n"
        "---\n\n"
        "# Test Good Skill\n\n"
        "This is a test skill. It exists only for smoke tests.\n\n"
        "## Usage\n\n"
        "Do not use in production.\n"
    )
    return skill


def make_bad_skill(tmp: Path) -> Path:
    """Skill with multiple violations (no frontmatter, wrong name)."""
    skill = tmp / "BadSkill_Name"  # wrong case + underscore
    skill.mkdir()
    (skill / "SKILL.md").write_text("# No frontmatter here\n")
    return skill


# --- Codex CLI selection and script entry points ---

def test_codex_command_override_precedes_path():
    sys.path.insert(0, str(SCRIPTS_DIR))
    try:
        import utils  # pyright: ignore[reportMissingImports]  # resolved at runtime via sys.path.insert above
        with tempfile.TemporaryDirectory() as tmp:
            executable = Path(tmp) / "Codex CLI" / "codex.exe"
            executable.parent.mkdir()
            executable.touch()
            with mock.patch.dict(os.environ, {"SKILL_CONDUCTOR_CODEX": str(executable)}):
                with mock.patch.object(utils.shutil, "which", return_value="path-codex.exe"):
                    assert utils.codex_command() == [str(executable)]
    finally:
        sys.path.pop(0)


def test_codex_command_handles_path_with_spaces():
    sys.path.insert(0, str(SCRIPTS_DIR))
    try:
        import utils  # pyright: ignore[reportMissingImports]  # resolved at runtime via sys.path.insert above
        with tempfile.TemporaryDirectory() as tmp:
            executable = Path(tmp) / "Codex CLI" / "codex.exe"
            executable.parent.mkdir()
            executable.touch()
            with mock.patch.dict(os.environ, {"SKILL_CONDUCTOR_CODEX": str(executable)}):
                assert utils.codex_command() == [str(executable)]
    finally:
        sys.path.pop(0)


def test_codex_version_uses_selected_cli():
    sys.path.insert(0, str(SCRIPTS_DIR))
    try:
        import utils  # pyright: ignore[reportMissingImports]  # resolved at runtime via sys.path.insert above
        with mock.patch.object(utils, "codex_command", return_value=["codex-test"]):
            with mock.patch.object(utils.subprocess, "run", return_value=mock.Mock(stdout="codex 1.2.3\n", returncode=0)) as run_cli:
                assert utils.codex_version() == "codex 1.2.3"
                run_cli.assert_called_once_with(
                    ["codex-test", "--version"], capture_output=True, text=True, check=True, timeout=10
                )
    finally:
        sys.path.pop(0)


def test_codex_environment_disables_desktop_app_tools():
    sys.path.insert(0, str(SCRIPTS_DIR))
    try:
        import utils  # pyright: ignore[reportMissingImports]  # resolved at runtime via sys.path.insert above
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = str(Path(tmp) / "codex-home")
            desktop_context = {
                "CODEX_APP_TOOLS_PIPE_PATH": "test-app-tools-pipe",
                "CODEX_INTERNAL_ORIGINATOR_OVERRIDE": "test-originator",
                "CODEX_SESSION_ID": "test-session",
                "CODEX_THREAD_ID": "test-thread",
                "CODEX_TOOL_CALL_ID": "test-tool-call",
            }
            with mock.patch.dict(os.environ, {
                **desktop_context,
                "CODEX_HOME": codex_home,
            }):
                env = utils.codex_environment(Path(tmp))
                assert all(name not in env for name in desktop_context)
                assert env["CODEX_HOME"] == codex_home
    finally:
        sys.path.pop(0)


def test_run_eval_help_as_script():
    result = subprocess.run(
        [UV_BIN, "run", str(SCRIPTS_DIR / "run_eval.py"), "--help"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, f"--help failed: {result.stderr}"


def test_run_loop_help_as_script():
    result = subprocess.run(
        [UV_BIN, "run", str(SCRIPTS_DIR / "run_loop.py"), "--help"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, f"--help failed: {result.stderr}"


def test_improve_description_help_as_script():
    result = subprocess.run(
        [UV_BIN, "run", str(SCRIPTS_DIR / "improve_description.py"), "--help"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, f"--help failed: {result.stderr}"


# --- run_eval JSONL classification ---

def _classify_trigger_events(events: list[dict], skill_path: Path):
    sys.path.insert(0, str(SCRIPTS_DIR))
    try:
        import run_eval  # pyright: ignore[reportMissingImports]  # resolved at runtime via sys.path.insert above
        return run_eval.classify_trigger_events(events, skill_path)
    finally:
        sys.path.pop(0)


def test_started_read_is_not_triggered():
    path = Path(r"C:\Temp\eval\.agents\skills\test-skill\SKILL.md")
    events = [{
        "type": "item.started",
        "item": {
            "type": "command_execution", "status": "in_progress",
            "command": f"Get-Content -LiteralPath '{path}' -Raw", "exit_code": None,
        },
    }]
    assert _classify_trigger_events(events, path).status == "not_triggered"


def test_successful_completed_read_is_triggered():
    path = Path(r"C:\Temp\eval\.agents\skills\test-skill\SKILL.md")
    events = [{
        "type": "item.completed",
        "item": {
            "type": "command_execution", "status": "completed",
            "command": f"Get-Content -LiteralPath '{path}' -Raw", "exit_code": 0,
        },
    }]
    assert _classify_trigger_events(events, path).status == "triggered"


def test_unrelated_command_containing_read_word_is_not_triggered():
    path = Path(r"C:\Temp\eval\.agents\skills\test-skill\SKILL.md")
    events = [{
        "type": "item.completed",
        "item": {
            "type": "command_execution", "status": "completed",
            "command": f"pwsh -Command \"Write-Output 'Get-Content {path}'\"", "exit_code": 0,
        },
    }]
    assert _classify_trigger_events(events, path).status == "not_triggered"


def test_failed_read_is_not_triggered():
    path = Path(r"C:\Temp\eval\.agents\skills\test-skill\SKILL.md")
    events = [{
        "type": "item.completed",
        "item": {
            "type": "command_execution", "status": "failed",
            "command": f"Get-Content -LiteralPath '{path}' -ErrorAction Stop", "exit_code": 1,
            "aggregated_output": "The path does not exist.",
        },
    }]
    assert _classify_trigger_events(events, path).status == "not_triggered"


def test_blocked_read_has_blocked_status():
    path = Path(r"C:\Temp\eval\.agents\skills\test-skill\SKILL.md")
    events = [{
        "type": "item.completed",
        "item": {
            "type": "command_execution", "status": "failed",
            "command": f"Get-Content -LiteralPath '{path}' -Raw", "exit_code": 1,
            "aggregated_output": "Blocked by the execution policy.",
        },
    }]
    assert _classify_trigger_events(events, path).status == "blocked"


def test_mcp_event_aborts_attempt():
    events = [{
        "type": "item.started",
        "item": {"type": "mcp_tool_call", "server": "sample", "tool": "probe", "arguments": {}},
    }]
    assert _classify_trigger_events(events, Path("SKILL.md")).status == "unexpected_tool_call"


def test_windows_skill_path_match_is_case_insensitive():
    path = Path(r"C:\Users\ARTEM\AppData\Local\Temp\eval\.agents\skills\test-skill\SKILL.md")
    command = r"Get-Content -LiteralPath 'c:\users\artem\appdata\local\temp\eval\.agents\skills\test-skill\skill.md' -Raw"
    events = [{
        "type": "item.completed",
        "item": {"type": "command_execution", "status": "completed", "command": command, "exit_code": 0},
    }]
    assert _classify_trigger_events(events, path).status == "triggered"


def _run_fake_codex(mode: str, tmp: Path, timeout: int = 5):
    fake_cli = tmp / "fake_codex.py"
    fake_cli.write_text(
        "import json, os, sys, time\n"
        "from pathlib import Path\n"
        "root = Path.cwd()\n"
        "Path(os.environ['SKILL_CONDUCTOR_TEST_PROJECT']).write_text(str(root))\n"
        "mode = os.environ['SKILL_CONDUCTOR_TEST_MODE']\n"
        "skill_path = root / '.agents' / 'skills' / 'test-skill' / 'SKILL.md'\n"
        "success = {'type': 'item.completed', 'item': {'type': 'command_execution', 'status': 'completed', 'command': f\"Get-Content -LiteralPath '{skill_path}' -Raw\", 'exit_code': 0}}\n"
        "mcp = {'type': 'item.started', 'item': {'type': 'mcp_tool_call', 'server': 'sample', 'tool': 'probe', 'arguments': {}}}\n"
        "if mode == 'success_then_mcp':\n"
        "    print(json.dumps(success), flush=True)\n"
        "    time.sleep(2)\n"
        "    Path(os.environ['SKILL_CONDUCTOR_TEST_CONTINUED']).write_text('continued')\n"
        "    print(json.dumps(mcp), flush=True)\n"
        "elif mode == 'mcp':\n"
        "    print(json.dumps(mcp), flush=True)\n"
        "elif mode == 'timeout':\n"
        "    time.sleep(5)\n"
        "elif mode == 'nonzero':\n"
        "    sys.exit(7)\n",
        encoding="utf-8",
    )
    project_record = tmp / "project-path.txt"
    continued_marker = tmp / "continued.txt"
    sys.path.insert(0, str(SCRIPTS_DIR))
    try:
        import run_eval  # pyright: ignore[reportMissingImports]  # resolved at runtime via sys.path.insert above
        with mock.patch.dict(os.environ, {
            "SKILL_CONDUCTOR_TEST_MODE": mode,
            "SKILL_CONDUCTOR_TEST_PROJECT": str(project_record),
            "SKILL_CONDUCTOR_TEST_CONTINUED": str(continued_marker),
        }):
            with mock.patch.object(run_eval, "codex_command", return_value=[sys.executable, str(fake_cli)]):
                attempt = run_eval.run_single_query("query", "test-skill", "test description", timeout)
        return attempt, project_record, continued_marker
    finally:
        sys.path.pop(0)


def test_stream_stops_after_successful_read():
    with tempfile.TemporaryDirectory() as tmp:
        attempt, project_record, continued_marker = _run_fake_codex("success_then_mcp", Path(tmp))
        assert attempt.status == "triggered"
        assert project_record.exists(), "fake CLI did not start"
        assert not Path(project_record.read_text()).exists(), "temporary Codex project was not deleted"
        assert not continued_marker.exists(), "runner processed events after confirmed read"


def test_timeout_has_timeout_status():
    with tempfile.TemporaryDirectory() as tmp:
        attempt, _, _ = _run_fake_codex("timeout", Path(tmp), timeout=1)
        assert attempt.status == "timeout"


def test_timeout_applies_after_stdout_closes():
    sys.path.insert(0, str(SCRIPTS_DIR))
    try:
        import run_eval  # pyright: ignore[reportMissingImports]  # resolved at runtime via sys.path.insert above

        class ClosedOutputProcess:
            stdin = mock.Mock()
            stdout = iter(())

            def __init__(self):
                self.returncode = None

            def poll(self):
                return self.returncode

            def wait(self, timeout=None):
                if self.returncode is not None:
                    return self.returncode
                if timeout is None:
                    raise AssertionError("CLI wait after stdout EOF must keep the query timeout")
                raise subprocess.TimeoutExpired("codex", timeout)

            def terminate(self):
                self.returncode = -15

            def kill(self):
                self.returncode = -9

        process = ClosedOutputProcess()
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(run_eval.subprocess, "Popen", return_value=process):
                attempt = run_eval.run_single_query("query", "test-skill", "test description", timeout=1)
        assert attempt.status == "timeout"
    finally:
        sys.path.pop(0)


def test_nonzero_cli_has_cli_error_status():
    with tempfile.TemporaryDirectory() as tmp:
        attempt, _, _ = _run_fake_codex("nonzero", Path(tmp))
        assert attempt.status == "cli_error"


def test_mcp_process_has_unexpected_tool_call_status():
    with tempfile.TemporaryDirectory() as tmp:
        attempt, _, _ = _run_fake_codex("mcp", Path(tmp))
        assert attempt.status == "unexpected_tool_call"


def _run_eval_with_attempts(attempts: list[object]) -> dict:
    sys.path.insert(0, str(SCRIPTS_DIR))
    try:
        import run_eval  # pyright: ignore[reportMissingImports]  # resolved at runtime via sys.path.insert above

        class Future:
            def __init__(self, attempt):
                self.attempt = attempt

            def result(self):
                return self.attempt

        class Pool:
            def __init__(self, max_workers):
                self.attempts = iter(attempts)

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def submit(self, *args):
                return Future(next(self.attempts))

        with mock.patch.object(run_eval, "ProcessPoolExecutor", Pool):
            with mock.patch.object(run_eval, "as_completed", side_effect=lambda futures: futures):
                return run_eval.run_eval(
                    eval_set=[{"query": "keyword research", "should_trigger": True}],
                    skill_name="test-skill", description="test", num_workers=1,
                    timeout=1, runs_per_query=len(attempts), trigger_threshold=0.5,
                )
    finally:
        sys.path.pop(0)


def test_infrastructure_failure_is_not_scored_as_no_trigger():
    sys.path.insert(0, str(SCRIPTS_DIR))
    try:
        import run_eval  # pyright: ignore[reportMissingImports]  # resolved at runtime via sys.path.insert above
        attempts = [run_eval.TriggerAttempt("triggered"), run_eval.TriggerAttempt("cli_error", detail="CLI missing")]
    finally:
        sys.path.pop(0)
    record = _run_eval_with_attempts(attempts)["results"][0]
    assert record["status"] == "incomplete"
    assert record["trigger_rate"] is None
    assert record["pass"] is None
    assert [attempt["status"] for attempt in record["attempts"]] == ["triggered", "cli_error"]
    assert "cli_error" in record["incomplete_reason"]

    complete = _run_eval_with_attempts([
        run_eval.TriggerAttempt("triggered"), run_eval.TriggerAttempt("not_triggered")
    ])["results"][0]
    assert complete["status"] == "complete"
    assert complete["trigger_rate"] == 0.5
    assert complete["triggers"] == 1
    assert complete["runs"] == 2
    assert complete["pass"] is True


def test_verbose_eval_labels_infrastructure_failure_incomplete():
    sys.path.insert(0, str(SCRIPTS_DIR))
    try:
        import run_eval  # pyright: ignore[reportMissingImports]  # resolved at runtime via sys.path.insert above
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill = make_good_skill(root)
            eval_file = root / "eval.json"
            eval_file.write_text(json.dumps([{"query": "keyword research", "should_trigger": True}]))
            output = {
                "summary": {"total": 1, "passed": 0, "failed": 0, "incomplete": 1},
                "results": [{
                    "query": "keyword research", "should_trigger": True,
                    "status": "incomplete", "trigger_rate": None, "triggers": 0,
                    "runs": 1, "pass": None, "incomplete_reason": "cli_error",
                }],
            }
            stderr = io.StringIO()
            argv = ["run_eval.py", "--eval-set", str(eval_file), "--skill-path", str(skill), "--verbose"]
            with mock.patch.object(run_eval, "run_eval", return_value=output):
                with mock.patch.object(sys, "argv", argv):
                    with redirect_stderr(stderr), redirect_stdout(io.StringIO()):
                        run_eval.main()
            assert "[INCOMPLETE]" in stderr.getvalue()
            assert "[FAIL]" not in stderr.getvalue()
    finally:
        sys.path.pop(0)


def test_incomplete_eval_stops_improvement_loop():
    sys.path.insert(0, str(SCRIPTS_DIR))
    try:
        import run_loop  # pyright: ignore[reportMissingImports]  # resolved at runtime via sys.path.insert above
        with tempfile.TemporaryDirectory() as tmp:
            skill = make_good_skill(Path(tmp))
            incomplete_eval = {
                "results": [{
                    "query": "keyword research", "should_trigger": True,
                    "status": "incomplete", "trigger_rate": None, "triggers": 0,
                    "runs": 1, "pass": None,
                    "attempts": [{"status": "cli_error", "evidence": None, "detail": "CLI missing"}],
                    "incomplete_reason": "1/1 attempts ended with cli_error",
                }],
                "summary": {"total": 1, "passed": 0, "failed": 0, "incomplete": 1},
            }
            with mock.patch.object(run_loop, "run_eval", return_value=incomplete_eval):
                with mock.patch.object(run_loop, "improve_description") as improve:
                    output = run_loop.run_loop(
                        eval_set=[{"query": "keyword research", "should_trigger": True}],
                        skill_path=skill, description_override=None, num_workers=1, timeout=1,
                        max_iterations=2, runs_per_query=1, trigger_threshold=0.5,
                        holdout=0, model=None, verbose=False,
                    )
            improve.assert_not_called()
            assert output["exit_reason"] == "incomplete_eval"
            assert output["incomplete_results"] == incomplete_eval["results"]
            assert "cli_error" in output["incomplete_reason"]
    finally:
        sys.path.pop(0)


def test_default_worker_count_is_one():
    sys.path.insert(0, str(SCRIPTS_DIR))
    try:
        import run_eval  # pyright: ignore[reportMissingImports]  # resolved at runtime via sys.path.insert above
        import run_loop  # pyright: ignore[reportMissingImports]  # resolved at runtime via sys.path.insert above
        assert run_eval.build_parser().get_default("num_workers") == 1
        assert run_loop.build_parser().get_default("num_workers") == 1
    finally:
        sys.path.pop(0)


# --- utils.parse_skill_md ---

def test_parse_good():
    sys.path.insert(0, str(SCRIPTS_DIR))
    try:
        import utils  # pyright: ignore[reportMissingImports]  # resolved at runtime via sys.path.insert above
        with tempfile.TemporaryDirectory() as tmp:
            skill = make_good_skill(Path(tmp))
            name, desc, content = utils.parse_skill_md(skill)
            assert name == "test-good-skill", f"name: {name}"
            assert "smoke testing" in desc, f"desc: {desc}"
            assert "# Test Good Skill" in content
    finally:
        sys.path.pop(0)


def test_parse_no_frontmatter_raises():
    sys.path.insert(0, str(SCRIPTS_DIR))
    try:
        import utils  # pyright: ignore[reportMissingImports]  # resolved at runtime via sys.path.insert above
        with tempfile.TemporaryDirectory() as tmp:
            skill = make_bad_skill(Path(tmp))
            try:
                utils.parse_skill_md(skill)
                raise AssertionError("expected ValueError on missing frontmatter")
            except ValueError:
                pass
    finally:
        sys.path.pop(0)


# --- eval_skill.py ---

def test_eval_skill_good_passes():
    with tempfile.TemporaryDirectory() as tmp:
        skill = make_good_skill(Path(tmp))
        result = subprocess.run(
            [UV_BIN, "run", str(SCRIPTS_DIR / "eval_skill.py"), str(skill)],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, f"exit {result.returncode}: {result.stderr}"
        assert "10/10" in result.stdout or "PASS" in result.stdout.upper(), \
            f"expected pass marker, got: {result.stdout[:300]}"


def test_eval_skill_bad_fails():
    with tempfile.TemporaryDirectory() as tmp:
        skill = make_bad_skill(Path(tmp))
        result = subprocess.run(
            [UV_BIN, "run", str(SCRIPTS_DIR / "eval_skill.py"), str(skill)],
            capture_output=True, text=True, timeout=30,
        )
        # bad skill must either exit non-zero or report failures
        combined = result.stdout + result.stderr
        assert result.returncode != 0 or "FAIL" in combined.upper() or "ERROR" in combined.upper(), \
            f"expected failure for bad skill, got: {combined[:300]}"


def test_eval_skill_detects_secret_leak():
    """Principle 9a: an env/secret in SKILL.md body must be flagged."""
    with tempfile.TemporaryDirectory() as tmp:
        skill = Path(tmp) / "leaky-skill"
        skill.mkdir()
        (skill / "SKILL.md").write_text(
            "---\n"
            "name: leaky-skill\n"
            "description: A test skill. Use when testing leak detection. Do NOT use in prod.\n"
            "---\n\n"
            "# Leaky Skill\n\n"
            "## Setup\n\n"
            "export API_KEY=sk-abcdef0123456789ABCDEF\n"
        )
        result = subprocess.run(
            [UV_BIN, "run", str(SCRIPTS_DIR / "eval_skill.py"), str(skill)],
            capture_output=True, text=True, timeout=30,
        )
        combined = (result.stdout + result.stderr).lower()
        assert "leak" in combined or "secret" in combined, \
            f"expected secret-leak warning, got: {result.stdout[:400]}"
        assert result.returncode != 0, "secret leak should fail the eval (non-zero exit)"


def test_eval_skill_list_description_no_crash():
    """A bracketed description parses as a YAML list — eval must fail gracefully, not crash."""
    with tempfile.TemporaryDirectory() as tmp:
        skill = Path(tmp) / "bracket-skill"
        skill.mkdir()
        (skill / "SKILL.md").write_text(
            "---\n"
            "name: bracket-skill\n"
            "description: [TODO: fill this in]\n"
            "---\n\n"
            "# Bracket Skill\n\n## Usage\n\nTest.\n"
        )
        result = subprocess.run(
            [UV_BIN, "run", str(SCRIPTS_DIR / "eval_skill.py"), str(skill)],
            capture_output=True, text=True, timeout=30,
        )
        assert "Traceback" not in result.stderr, f"eval crashed: {result.stderr[:400]}"
        assert "must be a string" in result.stdout, \
            f"expected non-string description failure, got: {result.stdout[:400]}"


def test_eval_skill_json_emits_all_det_ids():
    """--json on skill-conductor itself emits every deterministic question id exactly once, well-formed."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    try:
        import eval_skill  # pyright: ignore[reportMissingImports]  # resolved at runtime via sys.path.insert
        expected = set(eval_skill.DET_QUESTIONS.keys())
    finally:
        sys.path.pop(0)
    result = subprocess.run(
        [UV_BIN, "run", str(SCRIPTS_DIR / "eval_skill.py"), str(SKILL_DIR), "--json"],
        capture_output=True, text=True, timeout=30,
    )
    records = json.loads(result.stdout)
    ids = [r["id"] for r in records]
    assert len(ids) == len(set(ids)), f"duplicate ids: {ids}"
    assert set(ids) == expected, f"missing: {expected - set(ids)}; extra: {set(ids) - expected}"
    required = {"id", "dimension", "text", "violation_example", "source", "critical", "answer", "explanation"}
    for r in records:
        assert r["source"] == "deterministic", f"non-deterministic record: {r['id']}"
        assert set(r) >= required, f"record {r['id']} missing keys: {required - set(r)}"
        assert r["answer"] in (0, 1), f"bad answer for {r['id']}: {r['answer']}"


# --- quick_validate.py ---

def test_quick_validate_good_passes():
    with tempfile.TemporaryDirectory() as tmp:
        skill = make_good_skill(Path(tmp))
        result = subprocess.run(
            [UV_BIN, "run", str(SCRIPTS_DIR / "quick_validate.py"), str(skill)],
            capture_output=True, text=True, timeout=15,
        )
        assert result.returncode == 0, f"exit {result.returncode}: {result.stderr[:300]}"


def test_quick_validate_bad_fails():
    with tempfile.TemporaryDirectory() as tmp:
        skill = make_bad_skill(Path(tmp))
        result = subprocess.run(
            [UV_BIN, "run", str(SCRIPTS_DIR / "quick_validate.py"), str(skill)],
            capture_output=True, text=True, timeout=15,
        )
        assert result.returncode != 0, "expected non-zero exit on bad skill"


# --- init_skill.py ---

def test_init_skill_creates_structure():
    with tempfile.TemporaryDirectory() as tmp:
        result = subprocess.run(
            [UV_BIN, "run", str(SCRIPTS_DIR / "init_skill.py"),
             "smoke-init-test", "--path", tmp],
            capture_output=True, text=True, timeout=15,
        )
        assert result.returncode == 0, f"exit {result.returncode}: {result.stderr}"
        created = Path(tmp) / "smoke-init-test"
        assert created.exists(), f"skill dir not created at {created}"
        assert (created / "SKILL.md").exists(), "SKILL.md not created"
        # frontmatter should be valid
        content = (created / "SKILL.md").read_text()
        assert content.startswith("---"), "frontmatter missing"
        assert "name: smoke-init-test" in content, "name not set"


# --- package_skill.py ---

def test_package_skill_creates_zip():
    with tempfile.TemporaryDirectory() as tmp:
        skill = make_good_skill(Path(tmp))
        out_dir = Path(tmp) / "dist"
        out_dir.mkdir()
        result = subprocess.run(
            [UV_BIN, "run", str(SCRIPTS_DIR / "package_skill.py"),
             str(skill), str(out_dir)],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, f"exit {result.returncode}: {result.stderr[:500]}"
        produced = list(out_dir.glob("*.skill"))
        assert len(produced) == 1, f"expected 1 .skill file, got {len(produced)}: {produced}"
        # .skill should be a valid zip
        import zipfile
        assert zipfile.is_zipfile(produced[0]), f"{produced[0]} is not a zip"


# --- aggregate_benchmark.py (smoke: --help works) ---

def test_aggregate_benchmark_help():
    result = subprocess.run(
        [UV_BIN, "run", str(SCRIPTS_DIR / "aggregate_benchmark.py"), "--help"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, f"--help failed: {result.stderr}"
    assert "skill" in result.stdout.lower() or "benchmark" in result.stdout.lower()


# --- run all ---

def main():
    print("\nskill-conductor smoke tests\n" + "─" * 32)

    print("\nutils.parse_skill_md:")
    run("parses good skill", test_parse_good)
    run("raises on bad frontmatter", test_parse_no_frontmatter_raises)

    print("\nCodex CLI and script entry points:")
    run("explicit CLI override precedes PATH", test_codex_command_override_precedes_path)
    run("CLI override preserves paths with spaces", test_codex_command_handles_path_with_spaces)
    run("reports selected CLI version", test_codex_version_uses_selected_cli)
    run("eval hides the desktop app-tools bridge", test_codex_environment_disables_desktop_app_tools)
    run("run_eval --help works as script", test_run_eval_help_as_script)
    run("run_loop --help works as script", test_run_loop_help_as_script)
    run("improve_description --help works as script", test_improve_description_help_as_script)

    print("\nrun_eval JSONL classification:")
    run("started read is not a trigger", test_started_read_is_not_triggered)
    run("successful completed read triggers", test_successful_completed_read_is_triggered)
    run("unrelated command text is not a trigger", test_unrelated_command_containing_read_word_is_not_triggered)
    run("failed read is not a trigger", test_failed_read_is_not_triggered)
    run("blocked read is classified", test_blocked_read_has_blocked_status)
    run("MCP event aborts attempt", test_mcp_event_aborts_attempt)
    run("Windows skill path match ignores case", test_windows_skill_path_match_is_case_insensitive)
    run("stops after the successful read", test_stream_stops_after_successful_read)
    run("reports timeout distinctly", test_timeout_has_timeout_status)
    run("keeps timeout after stdout closes", test_timeout_applies_after_stdout_closes)
    run("reports nonzero CLI exit distinctly", test_nonzero_cli_has_cli_error_status)
    run("reports unexpected MCP call distinctly", test_mcp_process_has_unexpected_tool_call_status)

    print("\nrun_eval aggregation and loop safeguards:")
    run("infrastructure failure stays incomplete", test_infrastructure_failure_is_not_scored_as_no_trigger)
    run("verbose eval keeps incomplete distinct from failure", test_verbose_eval_labels_infrastructure_failure_incomplete)
    run("incomplete eval stops description optimization", test_incomplete_eval_stops_improvement_loop)
    run("default worker count is one", test_default_worker_count_is_one)

    print("\neval_skill.py:")
    run("good skill passes", test_eval_skill_good_passes)
    run("bad skill fails", test_eval_skill_bad_fails)
    run("detects secret leak", test_eval_skill_detects_secret_leak)
    run("list description no crash", test_eval_skill_list_description_no_crash)
    run("--json emits all DET ids", test_eval_skill_json_emits_all_det_ids)

    print("\nquick_validate.py:")
    run("good skill passes", test_quick_validate_good_passes)
    run("bad skill fails", test_quick_validate_bad_fails)

    print("\ninit_skill.py:")
    run("creates skill structure", test_init_skill_creates_structure)

    print("\npackage_skill.py:")
    run("creates valid .skill zip", test_package_skill_creates_zip)

    print("\naggregate_benchmark.py:")
    run("--help works", test_aggregate_benchmark_help)

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    total = len(RESULTS)
    print(f"\n{'─' * 32}\n{passed}/{total} passed")

    if passed != total:
        print("\nfailures:")
        for label, ok, err in RESULTS:
            if not ok:
                print(f"  - {label}: {err}")
        sys.exit(1)


if __name__ == "__main__":
    main()
