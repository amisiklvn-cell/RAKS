# Development Command Center — v1.0.1 status

The Development Command Center is **partly implemented**. It is a deterministic
planner, not a natural-language coding agent.

## What works now

- `/plan` lists the fixed intents and shows their steps.
- `/plan run INTENT` executes those steps through `ToolExecutor` using the
  normal approval gate.
- Plans are defined only for `status`, `history`, `backup`, `scan`, `tests` and
  `compile`.
- Unknown intents are refused with `NotImplementedError`; input is never
  translated into shell commands.

## What is still not implemented

- AI-driven interpretation of free-form requests into plans.
- Automatic extraction of paths, constraints or ambiguity from natural text.
- Dynamic tool creation or shell command generation.
- Automatic Git pushes, APK builds or issue creation from a plan.

These remain interface/design areas only. `TaskPlan`, `PlanStep`,
`ApprovalRequest` and `TaskResult` describe the intended shape but the current
planner does not use an AI model.

## Required flow for future work

1. **Understand the request**  
   `CommandInterpreter` classifies input; a future AI layer would extract
   intent, targets and ambiguity.

2. **Create a task plan**  
   A future planner would return `TaskPlan` objects with named tools.

3. **Show the plan**  
   The terminal must display the plan before anything happens. `/plan` already
   does this for fixed intents.

4. **Request approval**  
   Writes, builds and Git operations must ask `CLIApprovalGate` explicitly.

5. **Execute approved actions**  
   Only `ToolExecutor` may act, restricted to the approved workspace.

6. **Report honestly**  
   Failures are reported as failures; no simulated success.

7. **Save history**  
   Task summaries can be stored by `MemoryStore.record_task()` and shown with
   `/project list`. Logs keep only allowlisted metadata, never prompts or
   secret values.

## Non-goals

- No natural-language shell execution.
- No automatic Git pushes.
- No simulated AI reasoning.
- No writes outside the approved workspace.
