# Error Recovery & Retry Skill

## Skill: error-recovery

**Tier:** Gold
**Component:** Phase 1, Step 2
**Version:** 1.0.0

---

## Description

This skill enables resilient operation through automatic retry handling, circuit breaker patterns, and intelligent failure recovery. It ensures the AI Employee system can gracefully handle transient errors and recover from failures.

---

## Capabilities

### 1. Exponential Backoff Retry

Automatically retry failed operations with increasing delays:
- Configurable max retries (default: 5)
- Exponential delay growth (default: 2x per attempt)
- Jitter to prevent thundering herd
- Maximum delay cap (default: 60 seconds)

### 2. Circuit Breaker

Prevent cascading failures by tracking error patterns:
- Automatic circuit tripping after threshold failures
- Fast-fail when circuit is open
- Auto-recovery testing via half-open state

### 3. Failure Classification

Intelligent categorization of errors for optimal recovery:
- IO errors: Immediate retry
- Network errors: Exponential backoff
- API errors: Deferred retry
- System errors: Graceful degradation

### 4. Retry Queue

Deferred task storage and management:
- Persistent queue in `AI_Employee_Vault/Retry_Queue/`
- Automatic retry scheduling
- Task metadata and context preservation

---

## Usage

### Basic Retry Operation

```python
from utils.retry_handler import get_retry_handler

handler = get_retry_handler(actor="my_component")

result = handler.execute(
    my_function,
    arg1, arg2,
    task_id="operation_123",
    task_type="processing"
)
```

### With Circuit Breaker

```python
from utils.retry_handler import get_retry_handler, get_circuit_breaker

handler = get_retry_handler(
    actor="my_component",
    circuit_breaker="my_circuit"
)
circuit = get_circuit_breaker("my_circuit")

if circuit.can_execute():
    result = handler.execute(operation)
else:
    log("Circuit open - using fallback")
```

### Decorator Pattern

```python
@handler.with_retry(task_type="api_call")
def call_api(endpoint):
    return requests.get(endpoint).json()
```

---

## Integrated Components

| Script | Circuit Breaker Name |
|--------|---------------------|
| filesystem_watcher.py | filesystem_operations |
| agent_executor.py | task_processing |
| run_ai_employee.py | ai_employee |
| plan_creator.py | plan_creation |
| linkedin_poster.py | linkedin_posting |
| ceo_briefing_generator.py | ceo_briefing |
| email_server.py | email_operations |

---

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| max_retries | 5 | Maximum retry attempts |
| base_delay | 1.0s | Initial delay between retries |
| max_delay | 60.0s | Maximum delay cap |
| exponential_base | 2.0 | Delay multiplier per attempt |
| jitter_factor | 0.1 | Randomization range (±10%) |
| failure_threshold | 5 | Failures to open circuit |
| success_threshold | 3 | Successes to close circuit |

---

## Monitoring

### Check Circuit State
```python
state = circuit.get_state()
# Returns: {'state': 'CLOSED', 'failure_count': 0, ...}
```

### Check Retry Queue
```python
stats = queue_manager.get_queue_stats()
# Returns: {'total_tasks': 3, 'ready_for_retry': 1, ...}
```

---

## Files

| File | Purpose |
|------|---------|
| `utils/retry_handler.py` | Core implementation |
| `AI_Employee_Vault/Retry_Queue/` | Deferred task storage |
| `docs/ERROR_RECOVERY_SYSTEM.md` | Full documentation |

---

## Example Output

```
[2026-02-25 10:15:23] [INFO] Processing task...
[2026-02-25 10:15:24] [WARNING] Attempt 1 failed: Connection timeout
[2026-02-25 10:15:26] [WARNING] Attempt 2 failed: Connection timeout
[2026-02-25 10:15:30] [INFO] Attempt 3 succeeded
[2026-02-25 10:15:30] [INFO] Task completed successfully
Circuit State: CLOSED
```

---

## Related Skills

- `audit-logging.md` - All retries are logged via audit system
- `ai_employee_runner.md` - Orchestrates retry queue processing
- `ceo-briefing.md` - Reports system reliability metrics

---

## Troubleshooting

### Circuit Stuck Open
Wait for timeout or check failure logs for root cause.

### Queue Growing
Run `process_retry_queue(actor)` to process pending tasks.

### High Retry Rate
Review failure patterns - may indicate permanent errors.

---

*Gold Tier - Error Recovery & Retry System*
*Personal AI Employee Hackathon*
