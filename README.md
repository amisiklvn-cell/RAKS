# RAKS AI

**Version:** 0.1.0 (Stage 1 — terminal foundation)

RAKS AI is a personal assistant project for Android Termux. The long-term goal
is a hybrid assistant that can understand instructions, write code, manage
projects, run approved commands, and automate development tasks.

This release is deliberately **only the foundation**. It provides the terminal
shell, dashboard, command handling, safety boundaries, and architecture
interfaces. It does **not** provide an AI engine, tools, memory, browser UI, or
Git automation yet. Unimplemented features say so plainly instead of faking
intelligence.

## Launch

From the project directory:

```bash
cd ~/RAKS
python3 -m raks
```

Commands:

```
/help     show commands
/status   show system status
/clear    clear the screen
/menu     show the main menu
/exit     leave RAKS
1-10      open a menu section
```

## Requirements

- Android Termux on ARM64 (tested target: Redmi A3x)
- Python 3.9+
- No paid API, no model downloads, no Ollama, no Docker

RAKS uses only the Python standard library in Stage 1.

## Architecture

| Module | Responsibility | Stage 1 state |
| --- | --- | --- |
| `raks/ui.py` | Terminal rendering, colors, logo, prompt | Implemented |
| `raks/commands.py` | Classify input into actions | Implemented |
| `raks/app.py` | Main loop and dispatch | Implemented |
| `raks/system.py` | Lightweight system status | Implemented |
| `raks/logger.py` | Safe operation logging | Implemented |
| `raks/engine.py` | AI engine boundary | Not implemented |
| `raks/tools.py` | Tool executor boundary | Not implemented |
| `raks/memory.py` | Future SQLite memory | Not implemented |
| `raks/planner.py` | Development Command Center interfaces | Design only |

The interpreter, AI engine, and tool executor are separate modules. RAKS does
not depend on OpenCode at runtime; OpenCode is only the current development
helper.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and
[docs/COMMAND_CENTER.md](docs/COMMAND_CENTER.md).

## Safety rules

- Natural-language input is never executed as a shell command.
- File writes, installs, builds, and Git pushes will require explicit approval.
- Future file tools will be limited to `~/RAKS`.
- Secrets are never logged or committed.
- Backups are required before risky future modifications.

## Tests

```bash
cd ~/RAKS
python3 -m compileall -q raks tests
python3 -m unittest discover -v
```

## Roadmap

1. Terminal foundation and GitHub publishing **(current)**
2. AI engine and hybrid routing
3. SQLite memory
4. Browser interface
5. File and command tools
6. Coding agent
7. Debugging and building
8. Defensive cybersecurity
9. Automation and GitHub management
10. Testing and optimization

Stage 2 starts only after explicit approval.

## License

MIT — see [LICENSE](LICENSE).
