# RAKS v1.0.1 Operations

## Dependency order

```
config -> logger -> system
        -> providers -> engine
        -> memory
        -> approval -> tools
        -> core -> ui/app and web
        -> coding / security / automation / ops / planner
        -> integrated terminal commands
```

## Interfaces

Both interfaces construct or receive the same `RAKSCore`:

- `raks/app.py` — terminal loop, menus 1-10, 19 slash commands.
- `raks/web.py` — hardened stdlib HTTP server, loopback-only.

Browser endpoints:

```text
GET  /                         chat page with embedded session token
GET  /style.css                fixed in-memory stylesheet
GET  /app.js                   fixed in-memory frontend script
GET  /api/status               engine/memory/system status
GET  /api/history?limit=N&conversation_id=ID
GET  /api/conversations        list saved conversations
GET  /api/tools                list tool names
POST /api/chat                 {"prompt": "..."}
POST /api/conversations        {"title": "..."}
POST /api/conversations/switch {"id": "..."}
```

All `/api/*` routes require `X-RAKS-Token` plus the matching
`raks_session` cookie. POST routes additionally require a matching `Origin`
(or no `Origin` for non-browser clients), `Content-Type: application/json`,
and a body of at most 100,000 bytes. No tool-execution route exists.

## Logging policy

`logger.log()` accepts only an allowlist of fields: version, platform, action,
route, tool, mode, provider, endpoint, method, status and intent. Prompts,
conversation content, credentials, authorization headers, raw paths, titles,
tool arguments and unknown fields are discarded. Values resembling known
secret formats are redacted. `logger.sanitize_existing_log()` can rewrite older
log files to the same policy.

## AI routing

1. `auto`: use local provider if a CLI and model are configured; otherwise try
   online. If local inference fails, fall back to online.
2. `local`: only local; report an error if unavailable.
3. `online`: only online; never touch local.
4. `offline`: only local; never use the network.

No provider means an honest error, never a fabricated answer. Online mode
sends recent conversation messages to the selected external provider.

## Tool safety

`ToolExecutor` accepts only names from `TOOLS`. Every path is resolved under an
approved workspace. `execute_command` is explicitly disabled. Approval-gated
operations are rejected unless `CLIApprovalGate` receives `y`/`yes`. The test
approval gate lives only in `tests`, not in production code. `write_file`,
`delete_file`, `move_file` and `restore_backup` create or require backups;
unsafe archive members are skipped and counted. Deletion is limited to a
single file. `git_commit` requires explicit paths and never uses `git add -A`.

## Conversations

`MemoryStore` keeps a `state` table with the active conversation id. Starting
or switching a conversation updates that id; existing conversations are never
deleted or overwritten. Both the terminal (`/conversation`) and browser
(conversation selector) use the same core APIs.

## Verification commands

```bash
python3 -m compileall -q raks tests
python3 -m unittest discover -v
python3 -m raks <<'EOF'
/status
/conversation list
/plan backup
/project list
/history
/exit
EOF
```

## Resource measurement

`Menu 9` prints RSS via `/proc/self/status`, total/available RAM via
`/proc/meminfo` and free storage via `os.statvfs`. No continuous monitor or
background daemon is installed. Measured v1.0.1 process RSS was about 15–26 MB.

## Status of unfinished areas

| Area | Status |
| --- | --- |
| Local llama.cpp inference | Adapter implemented; no model or CLI installed, so unverified. |
| APK builds | Tool implemented; no Gradle/Android SDK, so never executed. |
| GitHub writes | Code exists in `ToolExecutor`; not exposed in the UI and not tested. |
| Web research | Online provider only; no dedicated crawler. |
| Natural-language planning | `/plan` supports only fixed named intents; no AI-driven planning. |

## Known limitations

- Local inference needs a user-installed llama.cpp CLI and model file.
- APK builds need an Android SDK and Gradle; RAKS only supplies the wrapper
  tool call and static source skeletons.
- Web research is limited to the optional online AI provider; no crawler.
- GitHub writes are available through named tools but RAKS never force-pushes.
- Cybersecurity is defensive inspection only; no exploitation or scanning of
  third-party hosts.
