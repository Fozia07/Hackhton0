# Ralph Wiggum Loop

## Overview

The Ralph Wiggum Loop is an autonomous multi-step task completion system. Named after the lovably persistent Simpsons character, it embodies the spirit of "never give up" - continuing to work on tasks until they're complete or definitively failed.

> "Me fail English? That's unpossible!" - Ralph Wiggum

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Ralph Wiggum Loop                         │
│                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │  Task Queue  │───▶│  Scheduler   │───▶│  Executor    │  │
│  │  (Priority)  │    │ (Dependencies)│    │  (Per-Type)  │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│         ▲                                       │           │
│         │                                       ▼           │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │    Retry     │◀───│    Result    │◀───│   Circuit    │  │
│  │    Queue     │    │   Handler    │    │   Breaker    │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
              ┌───────────────────────────────┐
              │       Task Executors          │
              ├───────────────────────────────┤
              │ • Social Post Executor        │
              │ • Campaign Executor           │
              │ • Accounting Audit Executor   │
              │ • CEO Briefing Executor       │
              │ • System Health Executor      │
              │ • Multi-Step Executor         │
              │ • Custom Command Executor     │
              └───────────────────────────────┘
```

## Features

### 1. Priority-Based Task Queue

Tasks are processed based on priority:
- **CRITICAL (1)**: Immediate execution
- **HIGH (2)**: Next in line
- **NORMAL (3)**: Standard processing
- **LOW (4)**: When time permits

### 2. Dependency Resolution

Tasks can specify dependencies that must complete first:

```python
task_audit = Task(
    id="audit_001",
    depends_on=["health_check_001"]  # Must wait for health check
)
```

### 3. Intelligent Retry Logic

Failed tasks are automatically retried:
- Default: 3 retry attempts
- Configurable per task
- Exponential backoff between retries

### 4. Circuit Breaker Protection

Prevents cascading failures:
- Triggers after 5 consecutive failures
- Stops all task processing
- Requires manual reset to continue
- Logs incident for review

### 5. Multi-Step Task Execution

Complex tasks can be broken into steps:

```python
Task(
    type=TaskType.MULTI_STEP,
    steps=[
        {"name": "Backup", "type": "command", "command": "backup.sh"},
        {"name": "Wait", "type": "delay", "seconds": 5},
        {"name": "Deploy", "type": "command", "command": "deploy.sh"}
    ]
)
```

## Task Types

| Type | Description | Executor |
|------|-------------|----------|
| `SOCIAL_POST` | Post to social media | SocialPostExecutor |
| `SOCIAL_CAMPAIGN` | Generate campaign | SocialCampaignExecutor |
| `ACCOUNTING_AUDIT` | Run accounting audit | AccountingAuditExecutor |
| `CEO_BRIEFING` | Generate CEO briefing | CEOBriefingExecutor |
| `SYSTEM_HEALTH_CHECK` | System health check | SystemHealthExecutor |
| `MULTI_STEP` | Multi-step tasks | MultiStepExecutor |
| `CUSTOM` | Custom commands | CustomExecutor |

## Task States

```
PENDING ──▶ IN_PROGRESS ──▶ COMPLETED
                │
                ▼
            FAILED ◀── RETRYING
                │
                ▼
            CANCELLED
```

## CLI Usage

### Check Status
```bash
python3 scripts/ralph_wiggum_loop.py --mode status
```

Output:
```
Loop State:
  Running: False
  Iterations: 5
  Completed: 4
  Failed: 0

Queue Status:
  Total: 4
  Pending: 0
  Completed: 4

Circuit Breaker:
  Triggered: False
  Consecutive Failures: 0/5
```

### Run Demo
```bash
python3 scripts/ralph_wiggum_loop.py --mode demo --verbose
```

Creates sample tasks and runs them to completion.

### Run Loop
```bash
python3 scripts/ralph_wiggum_loop.py --mode run --max-iterations 100
```

Processes all pending tasks until complete or max iterations reached.

### Reset
```bash
python3 scripts/ralph_wiggum_loop.py --mode reset
```

Resets circuit breaker and clears all tasks.

## Programmatic Usage

```python
from scripts.ralph_wiggum_loop import (
    RalphWiggumLoop, Task, TaskType, TaskPriority, TaskStatus
)

# Initialize loop
loop = RalphWiggumLoop()

# Create tasks
health_task = Task(
    id="health_001",
    type=TaskType.SYSTEM_HEALTH_CHECK,
    title="System Health Check",
    priority=TaskPriority.HIGH
)

audit_task = Task(
    id="audit_001",
    type=TaskType.ACCOUNTING_AUDIT,
    title="Weekly Audit",
    depends_on=["health_001"]  # Wait for health check
)

# Add to queue
loop.add_task(health_task)
loop.add_task(audit_task)

# Run until complete
results = loop.run_loop(max_iterations=50)

print(f"Completed: {results['tasks_completed']}")
print(f"Failed: {results['tasks_failed']}")
```

## File Structure

```
AI_Employee_Vault/
├── System/
│   ├── task_queue.json      # Current task queue
│   └── ralph_state.json     # Loop state
└── Logs/
    └── ralph_wiggum.log     # Execution log
```

## Log Format

Each log entry contains:
```json
{
  "timestamp": "2026-03-05T08:46:32.906000",
  "event": "task_completed",
  "task_id": "demo_health_001",
  "task_title": "System Health Check",
  "details": { ... }
}
```

## Circuit Breaker Details

The circuit breaker prevents runaway failures:

1. **Threshold**: 5 consecutive failures
2. **When Triggered**:
   - Loop stops immediately
   - State saved to `ralph_state.json`
   - Incident logged
3. **Recovery**:
   - Manual reset required: `--mode reset`
   - Review logs before resetting
   - Consider fixing underlying issues

## Integration Points

### With Social Media Orchestrator
```python
# Add posts to Ralph queue for guaranteed delivery
task = Task(
    type=TaskType.SOCIAL_POST,
    metadata={"platform": "twitter", "post_file": "post.md"}
)
loop.add_task(task)
```

### With Autonomous Controller
```python
# Trigger campaign through Ralph for reliability
task = Task(
    type=TaskType.SOCIAL_CAMPAIGN,
    priority=TaskPriority.HIGH
)
loop.add_task(task)
```

### With CEO Briefing
```python
# Weekly briefing as scheduled task
task = Task(
    type=TaskType.CEO_BRIEFING,
    depends_on=["accounting_audit", "social_analytics"]
)
loop.add_task(task)
```

## Best Practices

1. **Always check status** before adding critical tasks
2. **Use dependencies** to ensure proper execution order
3. **Monitor the log** for recurring failures
4. **Set appropriate priorities** - don't make everything CRITICAL
5. **Handle circuit breaker** events promptly
6. **Clear completed tasks** periodically with `--mode clear`

## Troubleshooting

### Tasks stuck in IN_PROGRESS
```bash
python3 scripts/ralph_wiggum_loop.py --mode reset
```

### Circuit breaker keeps triggering
1. Check `AI_Employee_Vault/Logs/ralph_wiggum.log`
2. Identify failing task type
3. Fix underlying issue
4. Reset and retry

### Dependencies not resolving
Ensure dependent task IDs match exactly:
```python
task1 = Task(id="exact_id_here", ...)
task2 = Task(depends_on=["exact_id_here"], ...)  # Must match!
```

---

*Part of AI Employee System - Gold Tier*
