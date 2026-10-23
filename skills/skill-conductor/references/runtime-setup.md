# Runtime setup (pre-flight)

Run `uv --version` before any mode that uses scripts. Run `codex login status` before automated trigger evals or description optimization. Sign in with `codex login` if needed.

Run script commands from the `skill-conductor` directory so imports and relative paths resolve. If `uv` is absent, stop and tell the user; do not run scripts directly with Python.

## Codex CLI access

`scripts/run_eval.py`, `scripts/run_loop.py`, and `scripts/improve_description.py` call `codex exec`. They use the logged-in Codex CLI account, so no Anthropic SDK or API key is required. Pass `--model <model-id>` to override Codex's default model.

Automated runs use `--json` for trigger traces, `--ephemeral` to avoid saving sessions, `--sandbox read-only` to prevent file writes, and `--ignore-user-config` to keep user MCP settings out of eval runs. They use a temporary home to hide global skills, while authentication still uses `CODEX_HOME`.

The eval runner places only candidate skill metadata in a temporary project under `.agents/skills/`, then removes it when the run ends. It does not add files to the skill being evaluated.
