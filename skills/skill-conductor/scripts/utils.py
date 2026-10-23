"""Shared utilities for skill-conductor scripts."""

import os
import random
import shutil
import subprocess
from pathlib import Path


def split_evals(
    items: list[dict], holdout: float, seed: int = 42, stratify_key: str | None = None
) -> tuple[list[dict], list[dict]]:
    """Split items into (train, test), optionally stratified by a key.

    Each stratum contributes max(1, int(len * holdout)) items to test, so no
    non-empty stratum is ever missing from the held-out set. Boolean strata are
    ordered truthy-first, which reproduces the historical run_loop.py
    should_trigger split bit-for-bit; other key values are ordered by str() so
    the split is independent of item order in the source file.
    """
    random.seed(seed)
    if stratify_key is None:
        strata = [list(items)]
    else:
        by_key: dict = {}
        for item in items:
            by_key.setdefault(item.get(stratify_key), []).append(item)
        if all(isinstance(k, bool) for k in by_key):
            order = sorted(by_key, reverse=True)
        else:
            order = sorted(by_key, key=str)
        strata = [by_key[k] for k in order]

    train: list[dict] = []
    test: list[dict] = []
    for stratum in strata:
        random.shuffle(stratum)
        n_test = max(1, int(len(stratum) * holdout))
        test += stratum[:n_test]
        train += stratum[n_test:]
    return train, test


def codex_command() -> list[str]:
    """Return a safe executable command for the Codex CLI."""
    override = os.environ.get("SKILL_CONDUCTOR_CODEX")
    if override:
        executable = Path(override).expanduser()
        if not executable.is_file():
            raise FileNotFoundError(f"SKILL_CONDUCTOR_CODEX does not point to a file: {override}")
        if os.name == "nt" and executable.suffix.lower() == ".ps1":
            powershell = shutil.which("pwsh") or shutil.which("powershell")
            if not powershell:
                raise FileNotFoundError("PowerShell is required to run the SKILL_CONDUCTOR_CODEX .ps1 file.")
            return [powershell, "-NoProfile", "-NonInteractive", "-File", str(executable)]
        return [str(executable)]

    if os.name == "nt":
        executable = shutil.which("codex.exe")
        if executable:
            return [executable]

        powershell = shutil.which("pwsh") or shutil.which("powershell")
        if powershell:
            for directory in os.environ.get("PATH", "").split(os.pathsep):
                candidate = Path(directory) / "codex.ps1"
                if candidate.is_file():
                    return [powershell, "-NoProfile", "-NonInteractive", "-File", str(candidate)]

    executable = shutil.which("codex")
    if executable and Path(executable).suffix.lower() not in {".bat", ".cmd"}:
        return [executable]

    raise FileNotFoundError("Codex CLI not found. Install it or add codex to PATH.")


def codex_version() -> str:
    """Return the version string of the selected Codex CLI."""
    result = subprocess.run(
        codex_command() + ["--version"], capture_output=True, text=True, check=True, timeout=10
    )
    return result.stdout.strip()


def codex_environment(isolated_home: Path) -> dict[str, str]:
    """Hide user skills/config while retaining the current Codex login."""
    env = os.environ.copy()
    for key in (
        "CODEX_APP_TOOLS_PIPE_PATH",
        "CODEX_INTERNAL_ORIGINATOR_OVERRIDE",
        "CODEX_SESSION_ID",
        "CODEX_THREAD_ID",
        "CODEX_TOOL_CALL_ID",
    ):
        env.pop(key, None)
    if not env.get("CODEX_HOME"):
        env["CODEX_HOME"] = str(Path.home() / ".codex")
    env["HOME"] = str(isolated_home)
    if os.name == "nt":
        env["USERPROFILE"] = str(isolated_home)
    return env


def parse_skill_md(skill_path: Path) -> tuple[str, str, str]:
    """Parse a SKILL.md file, returning (name, description, full_content)."""
    content = (skill_path / "SKILL.md").read_text()
    lines = content.split("\n")

    if lines[0].strip() != "---":
        raise ValueError("SKILL.md missing frontmatter (no opening ---)")

    end_idx = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        raise ValueError("SKILL.md missing frontmatter (no closing ---)")

    name = ""
    description = ""
    frontmatter_lines = lines[1:end_idx]
    i = 0
    while i < len(frontmatter_lines):
        line = frontmatter_lines[i]
        if line.startswith("name:"):
            name = line[len("name:"):].strip().strip('"').strip("'")
        elif line.startswith("description:"):
            value = line[len("description:"):].strip()
            # Handle YAML multiline indicators (>, |, >-, |-)
            if value in (">", "|", ">-", "|-"):
                continuation_lines: list[str] = []
                i += 1
                while i < len(frontmatter_lines) and (frontmatter_lines[i].startswith("  ") or frontmatter_lines[i].startswith("\t")):
                    continuation_lines.append(frontmatter_lines[i].strip())
                    i += 1
                description = " ".join(continuation_lines)
                continue
            else:
                description = value.strip('"').strip("'")
        i += 1

    return name, description, content
