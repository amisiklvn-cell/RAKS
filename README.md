# RAKS AI

**Version:** 1.0.0  
**Platform:** Android Termux, ARM64 (target device: Redmi A3x, 3 GB RAM)  
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

```
/web start        # prints http://127.0.0.1:8765
/web stop
/web status
```

Or directly:

```bash
python3 -c "from raks.core import RAKSCore; from raks.web import WebServer; s=WebServer(RAKSCore()); print(s.url); s.start(); s.httpd.serve_forever()"
```

## Commands

```
/help       show commands
/status     system status
/clear      clear screen
/menu       main menu
/exit       leave RAKS
/web        start|stop|status browser interface
/tools      list approved tools
/history    recent conversation
/backup     back up the workspace
/restore    list or restore backups
/security   defensive security scan
/code       languages | validate PATH | scaffold LANG DIR
/automate   run an automation (check, verify, snapshot)
/github     repository information
/config     show settings or set KEY VALUE
/ops        log | stats
1-10        open a menu section
text        send a request to the hybrid AI engine
```

## Features

| Area | Implementation |
| --- | --- |
| AI engine | Hybrid routing: local llama.cpp CLI first, free online provider fallback, honest offline errors |
| Memory | SQLite conversation history, tasks and project history in `~/.local/share/raks/raks.db` |
| Interfaces | Terminal UI and local browser chat, both backed by `RAKSCore` |
| Tools | Named operations only, workspace restricted, approval gates, backups before risky changes |
| Coding | Scaffold and statically validate Python, Java, JavaScript, HTML, CSS, Bash, JSON, XML, Android skeletons |
| Debugging | Compile, unittest, APK build tool (requires Gradle), GitHub status/log/diff |
| Security | Read-only defensive workspace scanner; no attacks, no network scanning |
| Automation | Named, deterministic task sequences; GitHub CLI integration with allowlisted commands |
| Operations | Backup, restore, settings, safe logging outside the repository |

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

Local inference requires a user-installed `llama-cli` (llama.cpp) and an
explicit model path. RAKS never downloads model weights.

## Safety

- Natural-language input is never executed as a shell command.
- Sensitive operations (writes, backups, restores, builds, commits, pushes,
  config changes) require explicit approval in the terminal.
- The browser interface denies approval-gated operations; it cannot silently
  approve them.
- File operations are restricted to approved workspaces (`~/RAKS` by default).
- Backups are made before overwrites and deletions. Nothing is auto-deleted.
- Credentials are never logged or committed. Logs contain event names only.
- No force-push is ever used.

## Storage layout (outside Git)

```
~/.config/raks/config.json        settings (0600)
~/.local/share/raks/raks.db       SQLite memory (0600)
~/.local/share/raks/backups/      backup archives
~/.local/state/raks/raks.log      event-only log
```

## Tests

```bash
cd ~/RAKS
python3 -m compileall -q raks tests
python3 -m unittest discover -v
```

## Documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- [docs/COMMAND_CENTER.md](docs/COMMAND_CENTER.md)
- [docs/OPERATIONS.md](docs/OPERATIONS.md)

## License

MIT — see [LICENSE](LICENSE).
