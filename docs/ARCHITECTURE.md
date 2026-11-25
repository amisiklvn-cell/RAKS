# RAKS AI architecture (v0.1.0)

## Goal

Keep reasoning, interpretation, and action separate so that RAKS can later
become independent of any external coding agent.

```
input -> CommandInterpreter -> RaksApp dispatch -> UI output
                                  |
                                  +-> AIEngine (Stage 2)
                                  +-> DevelopmentCommandCenter (design, Stage 9)
                                  +-> ToolExecutor (Stage 5+)
                                  +-> MemoryStore (Stage 3)
```

## Module boundaries

### `raks/commands.py`
Pure classification. It turns text into a `CommandResult` with an action such
as `help`, `status`, `menu_item`, or `chat`. It has no side effects and no
knowledge of AI or tools.

### `raks/ui.py`
Rendering only. It owns ANSI styling, the logo, the dashboard, and the
`raks >` prompt. It does not decide what actions mean.

### `raks/app.py`
The coordinator. It starts the UI, collects system status, reads input, asks
the interpreter to classify it, dispatches the action, and logs event names.

### `raks/engine.py`
The AI boundary. In v0.1.0 `respond()` always reports "not implemented". There
are no canned answers. Stage 2 will add local-first routing and optional
online fallback.

### `raks/tools.py`
The action boundary. v0.1.0 executes nothing. `APPROVAL_REQUIRED` records which
future operations must ask permission: file writes, installs, builds, Git
pushes, and shell commands.

### `raks/planner.py`
Interfaces for the future Development Command Center: `TaskPlan`, `PlanStep`,
`ApprovalRequest`, and `TaskResult`. Every entry point currently raises
`NotImplementedError`.

### `raks/memory.py`
Stage 3 boundary. SQLite will hold conversation history later; v0.1.0 creates
no database file.

### `raks/logger.py`
Writes short JSON event lines to `~/.local/state/raks/raks.log`, outside the
repository. Prompts and arguments are not logged.

## Resource policy

- Python standard library only.
- No Ollama, Docker, VMs, or model downloads.
- No paid API requirement.
- Model weights, if ever added, stay outside Git via `.gitignore`.

## Cybersecurity policy

Defensive use only. No offensive tooling is included or planned in this stage.
