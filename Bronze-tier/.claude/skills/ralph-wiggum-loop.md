# Ralph Wiggum Loop - Autonomous Task Completion

## Description
Enterprise-grade autonomous task completion system. Keeps working on tasks until they're done, handling failures gracefully with intelligent retry logic and circuit breakers.

"Me fail English? That's unpossible!" - Ralph Wiggum

## When to Use
- When multiple tasks need to be executed in sequence
- When tasks have dependencies on each other
- When you need autonomous task processing with retry logic
- When you need circuit breaker protection against cascading failures
- For batch processing of social media posts, audits, or reports

## Features
- **Task Queue**: Priority-based task queue with dependency resolution
- **Multi-Step Tasks**: Execute complex tasks with multiple steps
- **Retry Logic**: Automatic retry with configurable max attempts
- **Circuit Breaker**: Protection against infinite failure loops
- **Dependency Resolution**: Tasks wait for dependencies to complete
- **Comprehensive Logging**: Full audit trail of all operations

## Task Types
- `SOCIAL_POST` - Social media posting
- `SOCIAL_CAMPAIGN` - Campaign generation
- `SOCIAL_ANALYTICS` - Analytics processing
- `ACCOUNTING_AUDIT` - Odoo accounting audit
- `INVOICE_FOLLOWUP` - Invoice collection
- `EXPENSE_APPROVAL` - Expense processing
- `CEO_BRIEFING` - CEO briefing generation
- `SYSTEM_HEALTH_CHECK` - System health verification
- `MULTI_STEP` - Custom multi-step tasks
- `CUSTOM` - Generic command tasks

## CLI Usage

```bash
# Check current status
python3 scripts/ralph_wiggum_loop.py --mode status

# Run demo with sample tasks
python3 scripts/ralph_wiggum_loop.py --mode demo

# Run the loop (process all pending tasks)
python3 scripts/ralph_wiggum_loop.py --mode run --max-iterations 100

# Clear completed tasks
python3 scripts/ralph_wiggum_loop.py --mode clear

# Reset circuit breaker and clear all tasks
python3 scripts/ralph_wiggum_loop.py --mode reset
```

## Task Dependencies

Tasks can depend on other tasks. The loop automatically resolves dependencies:

```python
task1 = Task(id="health_check", ...)
task2 = Task(id="audit", depends_on=["health_check"], ...)
task3 = Task(id="briefing", depends_on=["audit"], ...)
```

## Circuit Breaker

Protection against cascading failures:
- Triggers after 5 consecutive failures
- Stops all task processing
- Requires manual reset: `--mode reset`

## File Locations

- **Task Queue**: `AI_Employee_Vault/System/task_queue.json`
- **Loop State**: `AI_Employee_Vault/System/ralph_state.json`
- **Logs**: `AI_Employee_Vault/Logs/ralph_wiggum.log`

## Integration Example

```python
from scripts.ralph_wiggum_loop import RalphWiggumLoop, Task, TaskType, TaskPriority

loop = RalphWiggumLoop()

# Add a task
task = Task(
    id="my_task",
    type=TaskType.CUSTOM,
    title="My Custom Task",
    description="Do something important",
    priority=TaskPriority.HIGH,
    metadata={"command": "echo 'Hello World'"}
)
loop.add_task(task)

# Run until complete
results = loop.run_loop()
```
