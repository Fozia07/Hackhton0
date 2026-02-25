# Audit Logging Skill

## Gold Tier Component

Use the centralized audit logging system to track all AI Employee operations.

---

## Overview

The audit logging system provides enterprise-grade, JSON-structured logging for all system operations. Every action is tracked with timestamps, actors, targets, and results.

---

## Quick Start

### Import the Logger

```python
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.audit_logger import (
    get_audit_logger,
    ActionType,
    ApprovalStatus,
    ResultStatus
)

# Initialize
ACTOR = "your_component_name"
audit_logger = get_audit_logger()
```

### Basic Logging

```python
# Log a simple action
audit_logger.log(
    action_type=ActionType.TASK_STARTED,
    actor=ACTOR,
    target="task_file.md",
    result=ResultStatus.SUCCESS
)
```

### Log with Parameters

```python
audit_logger.log(
    action_type=ActionType.TASK_COMPLETED,
    actor=ACTOR,
    target="email_task.md",
    parameters={
        'task_type': 'email',
        'destination': 'Done',
        'file_size': 1024
    },
    result=ResultStatus.SUCCESS
)
```

### Log with Duration

```python
start_time = datetime.now()
# ... perform operation ...
audit_logger.log_with_duration(
    action_type=ActionType.PLAN_CREATED,
    actor=ACTOR,
    target="PLAN_task_123.md",
    start_time=start_time,
    parameters={'complexity': 'high'},
    result=ResultStatus.SUCCESS
)
```

### Log Errors

```python
try:
    # ... operation that might fail ...
except Exception as e:
    audit_logger.log_error(
        actor=ACTOR,
        target=filename,
        error_message=str(e),
        error_type=type(e).__name__
    )
```

### Log with Approval Status

```python
audit_logger.log(
    action_type=ActionType.APPROVAL_REQUESTED,
    actor=ACTOR,
    target="linkedin_post.md",
    approval_status=ApprovalStatus.PENDING,
    result=ResultStatus.SUCCESS
)
```

---

## Action Types Reference

### System Events
- `ActionType.SYSTEM_STARTED` - Component startup
- `ActionType.SYSTEM_STOPPED` - Component shutdown
- `ActionType.HEALTH_CHECK` - Health verification

### Task Lifecycle
- `ActionType.INBOX_DETECTED` - New file in Inbox
- `ActionType.TASK_CREATED` - Metadata generated
- `ActionType.TASK_MOVED` - Task relocated
- `ActionType.TASK_STARTED` - Processing began
- `ActionType.TASK_COMPLETED` - Success
- `ActionType.TASK_FAILED` - Failure

### Approval Workflow
- `ActionType.APPROVAL_REQUESTED` - Awaiting approval
- `ActionType.APPROVAL_GRANTED` - Approved
- `ActionType.APPROVAL_DENIED` - Rejected

### Cycles
- `ActionType.CYCLE_STARTED` - Cycle began
- `ActionType.CYCLE_COMPLETED` - Cycle finished

### Specific Actions
- `ActionType.PLAN_CREATED` - Plan.md generated
- `ActionType.EMAIL_SENT` - Email sent
- `ActionType.EMAIL_DRAFTED` - Draft created
- `ActionType.LINKEDIN_POST` - Posted to LinkedIn
- `ActionType.CEO_BRIEFING_GENERATED` - Report generated

### Errors
- `ActionType.ERROR_OCCURRED` - General error

---

## Result Status

- `ResultStatus.SUCCESS` - Operation succeeded
- `ResultStatus.FAILURE` - Operation failed
- `ResultStatus.PARTIAL` - Partially completed
- `ResultStatus.PENDING` - In progress

---

## Approval Status

- `ApprovalStatus.NOT_REQUIRED` - No approval needed
- `ApprovalStatus.PENDING` - Awaiting approval
- `ApprovalStatus.APPROVED` - Approved
- `ApprovalStatus.REJECTED` - Rejected

---

## Best Practices

1. **Define ACTOR constant** at the top of your script
2. **Log system start/stop** for session tracking
3. **Use log_with_duration** for performance monitoring
4. **Include parameters** for context
5. **Call flush()** before script exits
6. **Handle errors gracefully** - log them, don't crash

---

## Log Storage

Logs are stored in: `AI_Employee_Vault/Logs/YYYY-MM-DD.json`

- Daily rotation
- 90-day retention
- Automatic cleanup

---

## View Logs

```bash
# View today's logs
cat AI_Employee_Vault/Logs/$(date +%Y-%m-%d).json | python3 -m json.tool

# Count entries
python3 -c "import json; print(len(json.load(open('AI_Employee_Vault/Logs/$(date +%Y-%m-%d).json'))))"
```

---

*Gold Tier Component - Personal AI Employee Hackathon*
