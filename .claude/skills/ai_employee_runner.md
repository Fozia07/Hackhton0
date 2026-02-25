# AI Employee Runner Skill

## Overview

Production-ready automated scheduler that runs the AI Employee system every 5 minutes. Handles task processing, workflow management, and autonomous operation without manual intervention.

## Skill Metadata

```yaml
name: ai_employee_runner
version: 1.0.0
tier: Silver
category: orchestration
trigger: scheduled (every 5 minutes)
dependencies:
  - plan_creator
  - approval_workflow
```

## Purpose

Automatically orchestrate the entire AI Employee workflow:
1. Monitor Inbox for new tasks
2. Process tasks in Needs_Action
3. Generate plans for complex tasks
4. Route tasks through approval workflow
5. Execute approved actions
6. Log all operations

## Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│              AI EMPLOYEE RUNNER - 5 MINUTE CYCLE                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. STARTUP                                                      │
│     └──► Load config, verify folders, check health              │
│                                                                  │
│  2. INBOX PROCESSING                                             │
│     └──► Scan /Inbox/* for new files                            │
│     └──► Create metadata, move to /Needs_Action                 │
│                                                                  │
│  3. TASK PROCESSING                                              │
│     └──► Read tasks from /Needs_Action                          │
│     └──► Analyze task type and priority                         │
│     └──► Generate Plan.md if complex                            │
│                                                                  │
│  4. APPROVAL CHECK                                               │
│     └──► Check /Pending_Approval for decisions                  │
│     └──► Process approved items                                 │
│     └──► Archive rejected items                                 │
│                                                                  │
│  5. EXECUTION                                                    │
│     └──► Execute approved actions                               │
│     └──► Move completed to /Done                                │
│                                                                  │
│  6. CLEANUP & LOGGING                                            │
│     └──► Archive old logs                                       │
│     └──► Update Dashboard.md                                    │
│     └──► Write execution log                                    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Configuration

### Environment Variables

```bash
# Required
AI_EMPLOYEE_VAULT=/path/to/AI_Employee_Vault

# Optional
AI_EMPLOYEE_LOG_LEVEL=INFO          # DEBUG, INFO, WARNING, ERROR
AI_EMPLOYEE_DRY_RUN=false           # true for testing
AI_EMPLOYEE_MAX_TASKS=10            # max tasks per cycle
AI_EMPLOYEE_TIMEOUT=300             # seconds per cycle
```

## Invocation

### Manual Run
```bash
python3 scripts/run_ai_employee.py
```

### With Options
```bash
python3 scripts/run_ai_employee.py --dry-run
python3 scripts/run_ai_employee.py --once
python3 scripts/run_ai_employee.py --verbose
```

### Scheduled Run (Cron)
```bash
*/5 * * * * cd /path/to/Bronze-tier && python3 scripts/run_ai_employee.py --once >> logs/cron.log 2>&1
```

## Error Handling

| Error Type | Recovery Action |
|------------|-----------------|
| File locked | Retry with backoff (3 attempts) |
| Invalid task | Move to /Rejected with error note |
| Network timeout | Queue for next cycle |
| Disk full | Alert and pause processing |
| Permission denied | Log and skip file |

## Logging

Logs are written to:
- `AI_Employee_Vault/Logs/YYYY-MM-DD_runner.json` - Structured logs
- `AI_Employee_Vault/Logs/runner.log` - Human-readable logs

## Health Checks

The runner performs health checks:
1. Verify all required folders exist
2. Check disk space (> 100MB free)
3. Validate file permissions
4. Test write capability

## Security

- Never processes files with executable extensions
- Validates all file paths (no directory traversal)
- Rate limits to prevent runaway execution
- Locks prevent concurrent runs

---

*AI Employee Runner Skill - Silver Tier*
*Production-Ready Automated Orchestration*
