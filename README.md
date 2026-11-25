# RAKS AI

**Version:** 1.0.1

**Platform:** Android Termux, ARM64 (target device: Redmi A3x, 3 GB RAM)

**Python:** 3.12 or newer (target environment: 3.14)

**Repository:** https://github.com/amisiklvn-cell/RAKS

RAKS AI is a hybrid, offline-first personal assistant for Android Termux. It
uses only the Python standard library, has no mandatory paid API, and never
downloads model weights. When no AI model or network is available, RAKS says so
plainly instead of pretending to be intelligent.

## Launch

```bash
cd ~/RAKS
python3 -m raks
```

Browser interface (same application core):

```text
/web start        # prints http://127.0.0.1:8765
/web stop
/web status
```

Open the printed URL in a browser on the same device. The page receives a
random per-session token embedded in its HTML; API calls send that token in an
`X-RAKS-Token` header together with a `SameSite=Strict` session cookie. The
server is loopback-only and rejects non-loopback configuration. The token
changes on every restart.

## Commands

```text
/help                        show commands
/status                      system status
/clear                       clear screen
/menu                        main menu
/exit                        leave RAKS
/web                         start|stop|status browser interface
/tools                       list approved tools
/history                     recent conversation
/backup                      back up the workspace
/restore                     list or restore backups
/security                    defensive security scan
/code                        languages | validate PATH | scaffold LANG DIR
/automate                    run an automation (check, verify, snapshot)
/github                      read-only repository information
/config                      show settings or set KEY VALUE
/ops                         log | stats
/conversation                list | new TITLE | switch ID
/plan                        list | run INTENT
/project                     list | add NAME PATH | task SUMMARY
1-10                         open a menu section
text                         send a request to the hybrid AI engine
```

## Feature status

| Area | Status | Notes |
| --- | --- | --- |
| Terminal UI and menus | Working and tested | 10 menus, 19 slash commands, real PTY verification. |
| Shared `RAKSCore` | Working and tested | Terminal and browser use the same engine, memory and tools. |
| Hybrid AI routing | Working and tested | `auto`, `local`, `online`, `offline`; honest errors when unavailable. |
| Local llama.cpp inference | Implemented, unverified | Requires a user-installed `llama-cli` and model; no weights downloaded. |
| Online AI provider | Working and tested | Free Pollinations default; optional OpenCode-compatible endpoint. |
| SQLite memory | Working and tested | Multiple isolated conversations, active conversation persists after restart. |
| Project/task memory | Working | Available through `/project`; not AI-generated. |
| Named tools | Working and tested | Allowlisted operations, workspace restriction, approval gates. |
| Backups and restore | Working and tested | Backups before risky writes; unsafe tar entries are counted and skipped. |
| Coding agent | Working and tested | Scaffold and static validation for 9 languages; no autonomous code generation. |
| APK build tool | Interface only | Returns an honest error without Gradle/Android SDK; build not executed. |
| Defensive security scan | Working and tested | Read-only workspace inspection; no exploitation or network scanning. |
| Automation center | Working and tested | `check`, `verify`, `snapshot` run named tools with approval. |
| GitHub read integration | Working and tested | `repo_info`, `commits`, `remote_head` via `gh`. |
| GitHub write tools | Interface only | Implemented in `ToolExecutor` but not exposed in the UI and not executed in tests. |
| Development Command Center | Working, limited | `/plan` shows and runs only fixed, named intents; no natural-language planning. |
| Web research | Placeholder | Online provider only; no dedicated crawler. |
| Browser chat/history | Working and tested | Token-authenticated, loopback-only, conversation selector. |

## AI configuration

Configuration lives in `~/.config/raks/config.json` (mode 0600). Secrets are
never stored there: only the *name* of an environment variable may be set.

```json
{
  "route_mode": "auto",
  "online_provider": "pollinations",
  "online_model": "openai",
  "online_key_env": "",
  "local_cli": "",
  "local_model": "",
  "request_timeout": 30,
  "web_host": "127.0.0.1",
  "web_port": 8765
}
```

`route_mode` values: `auto` (local then online), `local`, `online`, `offline`.
Environment overrides: `RAKS_ROUTE_MODE`, `RAKS_LOCAL_CLI`, `RAKS_LOCAL_MODEL`,
`RAKS_ONLINE_PROVIDER`, `RAKS_ONLINE_MODEL`, `RAKS_ONLINE_KEY_ENV`,
`RAKS_WEB_PORT`.

Free online default: Pollinations (`https://text.pollinations.ai/openai`).
An optional OpenCode-compatible endpoint is available with a public session or
a key supplied through `RAKS_ONLINE_KEY_ENV`. No key is required by default.
When online routing is used, recent conversation messages are sent to that
provider; use `offline` mode if you do not want this.

Local inference requires a user-installed `llama-cli` (llama.cpp) and an
explicit model path. RAKS never downloads model weights.

## Conversations

```text
/conversation list              show saved conversations
/conversation new work          start an isolated conversation
/conversation switch <id>       switch without deleting or overwriting others
```

The active conversation is stored in SQLite and restored after restarting
RAKS. The browser has a conversation selector backed by the same API.

## Safety

- Natural-language input is never executed as a shell command.
- Sensitive operations (writes, backups, restores, builds, commits, pushes,
  config changes) require explicit approval in the terminal.
- The browser has **no** tool-execution endpoint and cannot approve sensitive
  operations.
- File operations are restricted to approved workspaces (`~/RAKS` by default).
  Coding validation uses the same restriction.
- Backups are made before overwrites and deletions. Nothing is auto-deleted.
- `git_commit` requires explicit file paths; `git add -A` is disabled.
- Logs contain only event names and an allowlist of short metadata fields.
  Prompts, conversation content, credentials, authorization headers, raw paths
  and tool arguments are never logged; values resembling secrets are redacted.
- No force-push is ever used.

## Local web server security

- Binds only to `127.0.0.1`, `::1` or `localhost`; other hosts are rejected.
- Issues a random session token on every start.
- API requests require both the token header and the matching session cookie.
- State-changing requests validate `Origin` and reject `cross-site` fetches.
- JSON content type and request-size limits are enforced; errors are generic.
- Security headers (`CSP`, `nosniff`, `frame-deny`, `no-referrer`) are set.
- Only fixed in-memory `/`, `/style.css` and `/app.js` assets are served.

## Storage layout (outside Git)

```text
~/.config/raks/config.json        settings (0600)
~/.local/share/raks/raks.db       SQLite memory (0600)
~/.local/share/raks/backups/      backup archives
~/.local/state/raks/raks.log      privacy-filtered event log
```

## Tests

```bash
cd ~/RAKS
python3 -m compileall -q raks tests
python3 -m unittest discover -v
```

The suite covers browser history/API, secret redaction, authentication,
unauthorized requests, CSRF/origin validation, workspace restrictions,
backup/restore, AI routing, terminal commands and all existing features.

## Documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- [docs/COMMAND_CENTER.md](docs/COMMAND_CENTER.md)
- [docs/OPERATIONS.md](docs/OPERATIONS.md)

## License

MIT — see [LICENSE](LICENSE).
