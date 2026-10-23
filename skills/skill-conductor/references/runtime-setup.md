# Runtime setup (pre-flight)

Run `uv --version` before any mode that uses scripts. Run `codex login status` before automated trigger evals or description optimization. Sign in with `codex login` if needed. To select a specific Codex Desktop executable, set `SKILL_CONDUCTOR_CODEX` to its full `.exe` or `.ps1` path; spaces stay part of the path.

Run script commands from the `skill-conductor` directory. If `uv` is absent, stop and tell the user; do not run scripts directly with Python. Verify the local runtime with `uv run scripts/test_smoke.py`.

Supported entrypoints:

```bash
uv run scripts/run_eval.py --help
uv run scripts/run_loop.py --help
uv run scripts/improve_description.py --help
```

The same modules can also run with `uv run python -m scripts.run_eval --help`, `scripts.run_loop`, or `scripts.improve_description` from the skill directory.

## Codex CLI access

`scripts/run_eval.py`, `scripts/run_loop.py`, and `scripts/improve_description.py` call `codex exec`. They use the logged-in Codex CLI account, so no Anthropic SDK or API key is required. Pass `--model <model-id>` to override Codex's default model.

Trigger eval uses `codex exec --json --ephemeral --ignore-user-config --skip-git-repo-check --approve-for-me` in a temporary project. `--approve-for-me` uses the workspace-write sandbox, limited to that temporary project. The runner does not pass `--ignore-rules`.

Codex CLI documents `--ignore-user-config` as skipping `$CODEX_HOME/config.toml`; it does not disable `.rules` files. The runner removes Codex Desktop app pipe and session context variables (`CODEX_APP_TOOLS_PIPE_PATH`, `CODEX_INTERNAL_ORIGINATOR_OVERRIDE`, `CODEX_SESSION_ID`, `CODEX_THREAD_ID`, `CODEX_TOOL_CALL_ID`) to keep connected tools out of isolated trigger evals, and aborts if another MCP call appears before the test skill is read. Local smoke tests use a fake CLI and never call Codex, MCP, Apify, or SerpStat.

The eval runner places only candidate skill metadata in a temporary project under `.agents/skills/`, then removes it when the run ends. It does not add files to the skill being evaluated. Triggered means a completed `command_execution` successfully read the staged `SKILL.md`; a started command or failed read does not count. The timeout covers process exit even if the CLI closes stdout early.

Attempt statuses:

- `triggered`: completed read, exit code `0`.
- `not_triggered`: Codex completed without a successful read.
- `blocked`: a rule or approval blocked the attempt.
- `timeout`: Codex exceeded the per-query limit.
- `cli_error`: Codex failed to start, emitted invalid JSONL, or exited unsuccessfully.
- `unexpected_tool_call`: Codex emitted an MCP call before reading the test skill.

Any eval record containing a status other than `triggered` or `not_triggered` is `incomplete`. It has no trigger rate or pass score, and OPTIMIZE stops before description changes.
