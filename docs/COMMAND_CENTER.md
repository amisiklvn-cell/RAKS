# Development Command Center — design (not implemented)

This document describes the future system that will let you give RAKS
natural-language instructions such as "create a Python app", "fix errors in my
project", "build an APK", or "push approved changes to GitHub".

No part of this system is active in v0.1.0. The interfaces exist in
`raks/planner.py` so later stages can grow into them without coupling the UI,
AI, and tools together.

## Required flow

1. **Understand the request**  
   `CommandInterpreter` classifies the input. The AI engine extracts intent,
   target paths, constraints, and ambiguity.

2. **Create a task plan**  
   `DevelopmentCommandCenter.interpret()` returns a `TaskPlan` made of
   `PlanStep` objects. Each step names a tool, arguments, and whether approval
   is required.

3. **Show the plan**  
   The terminal displays the plan before anything happens. No hidden action.

4. **Request approval**  
   For writes, installs, builds, and Git pushes, RAKS calls
   `request_approval()` and waits for an explicit yes. A refusal cancels the
   step.

5. **Execute approved actions**  
   Only `ToolExecutor` may perform actions. It will refuse unapproved steps and
   restrict file operations to `~/RAKS`.

6. **Report honestly**  
   `TaskResult` records success or failure with the real output. RAKS will not
   claim success when a command failed.

7. **Save history**  
   Approved task summaries are written to SQLite memory in Stage 3. Logs keep
   event names only, never secret values.

## Example future plan

```text
Request: "Create a Python application in ~/RAKS/tools/hello"

Plan:
  1. inspect workspace            tool=inspect       approval=no
  2. create directory             tool=write_file    approval=yes
  3. write hello.py               tool=write_file    approval=yes
  4. run tests                    tool=execute       approval=yes
  5. report result                tool=report        approval=no
```

Steps 2–4 would wait for approval. There is no execution path in v0.1.0.

## Non-goals for this stage

- No natural-language shell execution.
- No automatic Git pushes.
- No simulated AI reasoning.
- No backups deletion or writes outside the approved workspace.
