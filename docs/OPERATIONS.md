# RAKS v1.0 Operations

## Dependency order

```
config -> logger -> system
       -> providers -> engine
       -> memory
       -> approval -> tools
       -> core -> ui/app and web
       -> coding / security / automation / ops
       -> integrated terminal commands
```

## Interfaces

Both interfaces construct or receive the same `RAKSCore`:

- `raks/app.py` — terminal loop, menus 1-10, slash commands.
- `raks/web.py` — stdlib HTTP server on 127.0.0.1, endpoints:
  - `GET /` chat page
  - `GET /api/status`
  - `GET /api/history?limit=N`
  - `GET /api/tools`
  - `POST /api/chat` with `{"prompt": "..."}`

Browser requests cannot approve sensitive tools (`DenyGate` is the safe default
for non-terminal interfaces).

## AI routing

1. `auto`: use local provider if a CLI and model are configured; otherwise try
   online. If local inference fails, fall back to online.
2. `local`: only local; report an error if unavailable.
3. `online`: only online; never touch local.
4. `offline`: only local; never use the network.

No provider means an honest error, never a fabricated answer.

## Tool safety

`ToolExecutor` accepts only names from `TOOLS`. Every path is resolved under an
approved workspace. `execute_command` is explicitly disabled. Approval-gated
operations are rejected unless `CLIApprovalGate` receives `y`/`yes`.
`write_file`, `delete_file`, `move_file` and `restore_backup` create or require
backups. Deletion is limited to a single file.

## Verification commands

```bash
python3 -m compileall -q raks tests
python3 -m unittest discover -v
python3 -m raks <<'EOF'
/status
/code languages
/history
/exit
EOF
```

## Resource measurement

`Menu 9` prints RSS via `/proc/self/status`, total/available RAM via
`/proc/meminfo` and free storage via `os.statvfs`. No continuous monitor or
background daemon is installed.

## Known limitations

- Local inference needs a user-installed llama.cpp CLI and model file.
- APK builds need an Android SDK and Gradle; RAKS only supplies the wrapper
  tool call and static source skeletons.
- Web research is limited to the optional online AI provider; no crawler.
- GitHub writes are available through named tools but RAKS never force-pushes.
- Cybersecurity is defensive inspection only; no exploitation or scanning of
  third-party hosts.
