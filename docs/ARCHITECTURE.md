# RAKS AI architecture (v1.0.1)

## Goal

Keep reasoning, interpretation, and action separate so that RAKS remains
independent of any external coding agent.

```
input -> CommandInterpreter -> RaksApp dispatch -> UI output
                                   |
                                   +-> HybridAIEngine -> providers
                                   +-> DevelopmentCommandCenter (fixed plans)
                                   +-> ToolExecutor (named, approved actions)
                                   +-> MemoryStore (SQLite conversations)
```

Both the terminal and browser construct or receive the same `RAKSCore`.

## Module boundaries

### `raks/commands.py`
Pure classification. It turns text into a `CommandResult` with an action such
as `help`, `status`, `menu_item`, `chat`, `conversation`, `plan` or `project`.
It has no side effects and no knowledge of AI or tools.

### `raks/ui.py`
Rendering only. It owns ANSI styling, the logo, the dashboard, and the
`raks >` prompt. It does not decide what actions mean.

### `raks/app.py`
The coordinator. It starts the UI, collects system status, reads input, asks
the interpreter to classify it, dispatches the action, and logs only safe
event names.

### `raks/engine.py` and `raks/providers.py`
The AI boundary. `respond()` routes between an optional local llama.cpp CLI
adapter and an optional online OpenAI-compatible provider. Missing providers
return an explicit error; no canned answers are generated.

### `raks/memory.py`
SQLite persistence for conversations, messages, tasks, projects and the active
conversation id. Conversation switching never deletes prior history.

### `raks/logger.py`
Privacy-filtered JSON event lines in `~/.local/state/raks/raks.log`, outside
the repository. Only allowlisted metadata fields are written and secret-like
values are redacted.

### `raks/tools.py` and `raks/approval.py`
The action boundary. Only names in `TOOLS` execute. Paths must resolve inside
an approved workspace, destructive operations require explicit approval, and
arbitrary command execution is disabled. The permissive approval gate exists
only in the test suite.

### `raks/web.py`
Local browser boundary. Loopback-only, per-session token, cookie plus header
authentication, origin validation, fixed in-memory assets, and no tool
execution endpoint.

### `raks/planner.py`
Deterministic plans for fixed named intents (`status`, `history`, `backup`,
`scan`, `tests`, `compile`). `/plan` displays them and `/plan run INTENT`
executes their named tools through the normal approval path. There is no
natural-language AI planner.

### `raks/coding.py`, `raks/security.py`, `raks/automation.py`, `raks/ops.py`
Scaffolding/static validation, read-only defensive inspection, named
automations with GitHub CLI read helpers, and backup/config/log operations.

## Resource policy

- Python standard library only.
- No Ollama, Docker, VMs, or model downloads.
- No paid API requirement.
- Model weights, if ever added, stay outside Git via `.gitignore`.

## Cybersecurity policy

Defensive use only. No offensive tooling is included. GitHub writes are never
force-pushed and are not exposed through the browser.
