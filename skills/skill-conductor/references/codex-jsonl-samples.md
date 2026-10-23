# Codex JSONL samples

These minimal records document the `codex exec --json` item shapes used by trigger eval. Prompts, file contents, and temporary user data are omitted.

## Successful read (captured with Codex CLI 0.163.0-alpha.11.2)

The CLI emitted an `item.started` record, then this completion. Only the completed event with status `completed` and exit code `0` proves the read finished:

```json
{"type":"item.completed","item":{"id":"item_1","type":"command_execution","status":"completed","command":"pwsh -Command \"Get-Content -LiteralPath '<TEMP>/.agents/skills/skill-conductor-probe/SKILL.md' -Raw\"","exit_code":0}}
```

## Failed read (captured with Codex CLI 0.163.0-alpha.11.2)

The command ran but the requested file did not exist:

```json
{"type":"item.completed","item":{"id":"item_1","type":"command_execution","status":"failed","command":"pwsh -Command \"Get-Content -LiteralPath '<TEMP>/.agents/skills/skill-conductor-probe/DOES-NOT-EXIST.md' -ErrorAction Stop\"","exit_code":1,"aggregated_output":"Get-Content: path does not exist"}}
```

## Blocked read (synthetic)

No project or user rule blocked a read in the disposable probe, so this inert fixture covers the explicit policy-denial shape without changing user rules:

```json
{"type":"item.completed","item":{"id":"item_1","type":"command_execution","status":"failed","command":"Get-Content -LiteralPath '<TEMP>/.agents/skills/skill-conductor-probe/SKILL.md' -Raw","exit_code":1,"aggregated_output":"Blocked by the execution policy."}}
```

## MCP call (synthetic)

No MCP tool was called. This inert fixture uses the CLI's documented MCP item type so the runner can reject the event without invoking a server:

```json
{"type":"item.started","item":{"id":"item_2","type":"mcp_tool_call","server":"sample","tool":"probe","arguments":{}}}
```
