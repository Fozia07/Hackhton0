# AI Employee Audit Logging System

## Gold Tier Feature

Version: 1.0.0
Author: AI Employee System
Classification: INTERNAL

---

## Overview

The Audit Logging System provides comprehensive, enterprise-grade logging for all AI Employee operations. Every significant action is tracked with structured JSON logs, enabling full visibility into system behavior, compliance reporting, and performance analysis.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      AI Employee Components                      │
├─────────────┬─────────────┬──────────────┬─────────────────────┤
│ filesystem  │   agent     │    plan      │     linkedin        │
│  _watcher   │  _executor  │   _creator   │     _poster         │
├─────────────┼─────────────┼──────────────┼─────────────────────┤
│ run_ai      │   ceo       │    email     │                     │
│ _employee   │ _briefing   │   _server    │                     │
└──────┬──────┴──────┬──────┴──────┬───────┴──────────┬──────────┘
       │             │             │                  │
       └─────────────┴─────────────┴──────────────────┘
                              │
                    ┌─────────▼─────────┐
                    │   AuditLogger     │
                    │  (utils/audit_    │
                    │   logger.py)      │
                    └─────────┬─────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
   ┌──────────────────────┐     ┌──────────────────────┐
   │  AI_Employee_Vault/  │     │   Auto-cleanup       │
   │  Logs/               │     │   (90-day retention) │
   │  YYYY-MM-DD.json     │     │                      │
   └──────────────────────┘     └──────────────────────┘
```

---

## Log Storage

### Location

All audit logs are stored in:
```
AI_Employee_Vault/Logs/YYYY-MM-DD.json
```

### File Format

Each daily log file contains a JSON array of log entries:

```json
[
  {
    "timestamp": "2026-02-24T10:30:45.123456",
    "action_type": "task_completed",
    "actor": "agent_executor",
    "target": "email_task.md",
    "parameters": {
      "task_type": "email",
      "destination": "Done"
    },
    "approval_status": "approved",
    "result": "success",
    "error": null,
    "duration_seconds": 1.234
  }
]
```

### Retention Policy

- **Retention Period:** 90 days
- **Auto-cleanup:** Logs older than 90 days are automatically deleted
- **Cleanup Trigger:** On AuditLogger initialization and daily at first log write

---

## Log Entry Structure

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | ISO 8601 | When the action occurred |
| `action_type` | String | Type of action (see Action Types) |
| `actor` | String | Component that performed the action |
| `target` | String | Resource affected by the action |
| `result` | String | Outcome: success, failure, partial, pending |

### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `parameters` | Object | Additional context data |
| `approval_status` | String | not_required, pending, approved, rejected |
| `error` | String | Error message if failed |
| `duration_seconds` | Float | Time taken for the action |

---

## Action Types

### System Events
- `system_started` - Component startup
- `system_stopped` - Component shutdown
- `health_check` - System health verification

### Task Lifecycle
- `inbox_detected` - New file detected in Inbox
- `task_created` - Metadata file created
- `task_moved` - Task moved between folders
- `task_started` - Processing began
- `task_completed` - Task finished successfully
- `task_failed` - Task failed with error

### Approval Workflow
- `approval_requested` - Human approval needed
- `approval_granted` - Human approved action
- `approval_denied` - Human rejected action

### Execution Cycles
- `cycle_started` - Processing cycle began
- `cycle_completed` - Processing cycle finished

### Specific Actions
- `plan_created` - Plan.md generated
- `email_sent` - Email dispatched
- `email_drafted` - Draft email created
- `linkedin_post` - LinkedIn post published
- `ceo_briefing_generated` - CEO report created

### Error Handling
- `error_occurred` - General error
- `warning_raised` - Warning logged
- `recovery_attempted` - Error recovery tried
- `recovery_succeeded` - Recovery successful

---

## Component Integration

### Adding Audit Logging to a Script

1. **Import the logger:**
```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.audit_logger import (
    get_audit_logger,
    ActionType,
    ApprovalStatus,
    ResultStatus
)

# Initialize
ACTOR = "your_script_name"
audit_logger = get_audit_logger()
```

2. **Log actions:**
```python
# Simple log
audit_logger.log(
    action_type=ActionType.TASK_STARTED,
    actor=ACTOR,
    target=filename,
    parameters={'key': 'value'},
    result=ResultStatus.SUCCESS
)

# Log with duration
start_time = datetime.now()
# ... do work ...
audit_logger.log_with_duration(
    action_type=ActionType.TASK_COMPLETED,
    actor=ACTOR,
    target=filename,
    start_time=start_time,
    result=ResultStatus.SUCCESS
)

# Log error
audit_logger.log_error(
    actor=ACTOR,
    target=filename,
    error_message=str(e),
    error_type=type(e).__name__
)
```

3. **Flush on exit:**
```python
audit_logger.flush()
```

---

## Integrated Components

| Component | Actor Name | Key Actions Logged |
|-----------|------------|-------------------|
| filesystem_watcher.py | filesystem_watcher | inbox_detected, task_moved, task_created |
| agent_executor.py | agent_executor | task_started, task_completed, task_failed |
| run_ai_employee.py | ai_employee_runner | cycle_started, cycle_completed, all task lifecycle |
| plan_creator.py | plan_creator | plan_created |
| linkedin_poster.py | linkedin_poster | approval_requested, linkedin_post |
| ceo_briefing_generator.py | ceo_briefing_generator | ceo_briefing_generated |
| email_server.py | email_mcp_server | email_sent, email_drafted |

---

## Technical Features

### Thread Safety
- File locking using `fcntl` (Unix) with Windows fallback
- Thread-safe singleton pattern
- Buffered writes with configurable flush size

### Atomic Writes
- Writes to temporary file first
- Renames to final location atomically
- Prevents log corruption on crashes

### Graceful Failure
- Logging failures don't crash the main application
- Errors are printed to stderr but operations continue
- Automatic retry with backoff

### Performance
- Default buffer size: 10 entries
- Automatic flush on buffer full
- Manual flush available for immediate writes

---

## CLI Testing

Test the audit logger directly:

```bash
# Run audit logger CLI
python3 utils/audit_logger.py

# Check recent logs
cat AI_Employee_Vault/Logs/$(date +%Y-%m-%d).json | python3 -m json.tool
```

---

## Log Analysis

### Count actions by type:
```bash
cat AI_Employee_Vault/Logs/*.json | \
  python3 -c "import json,sys,collections; \
    entries=[e for f in sys.stdin for e in json.loads(f.read())]; \
    print(collections.Counter(e['action_type'] for e in entries))"
```

### Find errors:
```bash
grep -l '"result": "failure"' AI_Employee_Vault/Logs/*.json
```

### View recent activity:
```bash
tail -100 AI_Employee_Vault/Logs/$(date +%Y-%m-%d).json | python3 -m json.tool
```

---

## Compliance & Security

### Data Captured
- All system operations
- User approval decisions
- Error conditions
- Performance metrics

### Data NOT Captured
- Email content (only metadata)
- LinkedIn post content (only references)
- Credentials or secrets
- Personal identifiable information

### Access Control
- Logs stored within AI_Employee_Vault
- Same access permissions as vault files
- No external transmission

---

## Best Practices

1. **Always log system start/stop** - Provides session boundaries
2. **Use consistent actor names** - Enables filtering by component
3. **Include relevant parameters** - Context aids debugging
4. **Log both success and failure** - Complete audit trail
5. **Flush before exit** - Ensure all logs are written
6. **Use duration logging** - Performance monitoring

---

## Future Enhancements

- [ ] Log aggregation service integration
- [ ] Real-time alerting on errors
- [ ] Log visualization dashboard
- [ ] Compliance report generation
- [ ] Log encryption at rest
- [ ] Remote log backup

---

*Gold Tier Component - Personal AI Employee Hackathon*
