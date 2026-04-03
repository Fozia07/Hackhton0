# Error Recovery & Retry System

## Gold Tier Component - Phase 1, Step 2

**Version:** 1.0.0
**Status:** Implemented
**Author:** AI Employee System

---

## Overview

The Error Recovery & Retry System provides enterprise-grade resilience for the AI Employee system. It implements exponential backoff with jitter, circuit breaker patterns, failure classification, and automatic task re-queueing to ensure reliable operation even under adverse conditions.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Error Recovery System                         │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────────┐  ┌──────────────────┐  ┌───────────────┐ │
│  │  Retry Handler   │  │ Circuit Breaker  │  │ Retry Queue   │ │
│  │  - Exp. Backoff  │  │ - Failure Track  │  │ - Task Store  │ │
│  │  - Jitter        │  │ - State Machine  │  │ - Metadata    │ │
│  │  - Max Retries   │  │ - Auto Recovery  │  │ - Deferred    │ │
│  └──────────────────┘  └──────────────────┘  └───────────────┘ │
│                              │                                   │
│  ┌──────────────────────────┴───────────────────────────────┐  │
│  │                  Failure Classifier                        │  │
│  │  - IO Errors → Immediate Retry                            │  │
│  │  - Network Errors → Exponential Backoff                   │  │
│  │  - API Errors → Deferred Retry                            │  │
│  │  - System Errors → Graceful Skip                          │  │
│  └────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Components

### 1. RetryHandler

The core retry mechanism implementing exponential backoff with jitter.

**Configuration:**
```python
RetryConfig(
    max_retries=5,           # Maximum retry attempts
    base_delay=1.0,          # Base delay in seconds
    max_delay=60.0,          # Maximum delay cap
    exponential_base=2.0,    # Exponential multiplier
    jitter_factor=0.1        # Jitter range (±10%)
)
```

**Delay Calculation:**
```
delay = base_delay × (exponential_base ^ attempt)
delay = min(delay, max_delay)
jitter = random(-jitter_factor, +jitter_factor) × delay
final_delay = delay + jitter
```

**Usage:**
```python
from utils.retry_handler import get_retry_handler

retry_handler = get_retry_handler(
    actor="my_component",
    circuit_breaker="my_circuit"
)

# Execute with automatic retry
result = retry_handler.execute(
    my_function,
    arg1, arg2,
    task_id="unique_id",
    task_type="operation_type"
)
```

### 2. Circuit Breaker

Prevents cascading failures by tracking failure patterns and temporarily blocking operations.

**States:**
- **CLOSED**: Normal operation, all requests pass through
- **OPEN**: Circuit tripped, requests blocked (fails fast)
- **HALF_OPEN**: Testing if service recovered

**Configuration:**
```python
failure_threshold=5        # Failures before opening circuit
success_threshold=3        # Successes needed to close circuit
timeout_seconds=60         # Time before trying half-open
```

**State Transitions:**
```
                 ┌────────────────┐
                 │     CLOSED     │
                 │  (Normal Ops)  │
                 └───────┬────────┘
                         │
          Failure Count >= Threshold
                         │
                         ▼
                 ┌────────────────┐
        ┌────────│      OPEN      │◄─────────┐
        │        │ (Blocking Ops) │          │
        │        └───────┬────────┘          │
        │                │                   │
        │         Timeout Elapsed            │
        │                │                   │
        │                ▼                   │
        │        ┌────────────────┐          │
        │        │   HALF_OPEN    │──────────┘
        │        │   (Testing)    │  Any Failure
        │        └───────┬────────┘
        │                │
        │     Success Count >= Threshold
        │                │
        └────────────────┴───────────────────┐
                         │                   │
                         ▼                   │
                 ┌────────────────┐          │
                 │     CLOSED     │◄─────────┘
                 └────────────────┘
```

### 3. Failure Classifier

Categorizes exceptions to determine appropriate recovery strategy.

**Failure Types:**
| Type | Examples | Recovery Mode |
|------|----------|---------------|
| IO | FileNotFoundError, PermissionError | Immediate Retry |
| NETWORK | ConnectionError, TimeoutError | Exponential Backoff |
| EXTERNAL_API | HTTPError, APIError | Deferred Retry |
| TRANSIENT | TemporaryError | Immediate Retry |
| PERMANENT | ValidationError, ValueError | Skip (No Retry) |
| RESOURCE | MemoryError, DiskFullError | System Degradation |
| UNKNOWN | Other exceptions | Exponential Backoff |

**Recovery Modes:**
| Mode | Behavior |
|------|----------|
| IMMEDIATE_RETRY | Retry immediately (no delay) |
| EXPONENTIAL_BACKOFF | Retry with increasing delays |
| DEFERRED_RETRY | Queue for later retry |
| GRACEFUL_SKIP | Log error and continue |
| SYSTEM_DEGRADATION | Alert and reduce load |

### 4. Retry Queue Manager

Manages deferred retry tasks stored in `AI_Employee_Vault/Retry_Queue/`.

**Task Metadata:**
```json
{
  "task_id": "unique_id",
  "task_type": "operation_type",
  "created_at": "2026-02-25T10:00:00",
  "retry_count": 2,
  "max_retries": 5,
  "last_attempt": "2026-02-25T10:05:00",
  "next_retry": "2026-02-25T10:10:00",
  "failure_type": "NETWORK",
  "error_message": "Connection timeout",
  "status": "pending",
  "actor": "filesystem_watcher",
  "context": { ... }
}
```

---

## Integrated Components

The retry system is integrated into all major scripts:

| Component | Circuit Breaker | Retry Types |
|-----------|-----------------|-------------|
| filesystem_watcher.py | filesystem_operations | File moves, metadata creation |
| agent_executor.py | task_processing | Task execution, status updates |
| run_ai_employee.py | ai_employee | Cycle orchestration |
| plan_creator.py | plan_creation | Plan generation |
| linkedin_poster.py | linkedin_posting | Browser automation, API calls |
| ceo_briefing_generator.py | ceo_briefing | Report generation |
| email_server.py | email_operations | Gmail API calls |

---

## Usage Examples

### Basic Retry
```python
from utils.retry_handler import get_retry_handler

handler = get_retry_handler(actor="my_script")

# Execute with retry
result = handler.execute(
    my_function,
    arg1, arg2,
    task_id="task_001",
    task_type="processing"
)
```

### With Circuit Breaker Check
```python
from utils.retry_handler import get_retry_handler, get_circuit_breaker

handler = get_retry_handler(actor="my_script", circuit_breaker="my_circuit")
circuit = get_circuit_breaker("my_circuit")

# Check circuit before operation
if not circuit.can_execute():
    print("Circuit open - operation blocked")
    return None

try:
    result = handler.execute(my_function, ...)
    circuit.record_success()
except Exception as e:
    circuit.record_failure(e)
    raise
```

### Processing Retry Queue
```python
from utils.retry_handler import process_retry_queue, get_queue_manager

# Process all ready tasks
results = process_retry_queue(actor="my_script")

# Get queue statistics
queue_manager = get_queue_manager()
stats = queue_manager.get_queue_stats()
print(f"Total tasks: {stats['total_tasks']}")
print(f"Ready for retry: {stats['ready_for_retry']}")
```

### Decorator Usage
```python
from utils.retry_handler import get_retry_handler

handler = get_retry_handler(actor="my_script")

@handler.with_retry(task_type="api_call")
def call_external_api(endpoint, data):
    response = requests.post(endpoint, json=data)
    response.raise_for_status()
    return response.json()
```

---

## Monitoring & Observability

### Circuit Breaker Status
```python
circuit = get_circuit_breaker("my_circuit")
state = circuit.get_state()

print(f"State: {state['state']}")
print(f"Failure Count: {state['failure_count']}")
print(f"Success Count: {state['success_count']}")
print(f"Last Failure: {state['last_failure_time']}")
```

### Retry Queue Monitoring
```python
queue_manager = get_queue_manager()
stats = queue_manager.get_queue_stats()

print(f"Total Tasks: {stats['total_tasks']}")
print(f"Pending: {stats['pending']}")
print(f"Ready for Retry: {stats['ready_for_retry']}")
print(f"By Type: {stats['by_type']}")
```

### Audit Integration

All retry operations are logged via the audit logger:

- `RETRY_ATTEMPTED` - Each retry attempt
- `RETRY_EXHAUSTED` - All retries failed
- `TASK_QUEUED` - Task added to retry queue
- `WARNING_RAISED` - Circuit breaker open

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| RETRY_MAX_RETRIES | 5 | Maximum retry attempts |
| RETRY_BASE_DELAY | 1.0 | Base delay in seconds |
| RETRY_MAX_DELAY | 60.0 | Maximum delay cap |
| RETRY_JITTER_FACTOR | 0.1 | Jitter range (±10%) |
| CIRCUIT_FAILURE_THRESHOLD | 5 | Failures to open circuit |
| CIRCUIT_SUCCESS_THRESHOLD | 3 | Successes to close circuit |
| CIRCUIT_TIMEOUT | 60 | Seconds before half-open |

### Per-Component Configuration

Each component can have custom retry settings:

```python
from utils.retry_handler import RetryConfig, RetryHandler

custom_config = RetryConfig(
    max_retries=10,
    base_delay=0.5,
    max_delay=120.0
)

handler = RetryHandler(config=custom_config, actor="custom_component")
```

---

## Error Handling Best Practices

### 1. Always Check Circuit Breaker
```python
if not circuit_breaker.can_execute():
    log("Circuit open - skipping operation")
    return graceful_fallback()
```

### 2. Record Success/Failure
```python
try:
    result = retry_handler.execute(operation)
    circuit_breaker.record_success()
    return result
except Exception as e:
    circuit_breaker.record_failure(e)
    raise
```

### 3. Use Task IDs for Traceability
```python
result = retry_handler.execute(
    operation,
    task_id=f"op_{unique_identifier}_{timestamp}",
    task_type="operation_category"
)
```

### 4. Handle Graceful Degradation
```python
try:
    result = retry_handler.execute(primary_operation)
except Exception:
    # Fallback to degraded mode
    result = fallback_operation()
    log("Operating in degraded mode")
```

---

## Troubleshooting

### Circuit Stuck Open

**Symptoms:** Operations consistently blocked with "circuit breaker open" message.

**Solution:**
1. Check failure logs for root cause
2. Fix underlying issue
3. Wait for timeout or manually reset:
```python
circuit_breaker._state = CircuitState.HALF_OPEN
```

### Retry Queue Growing

**Symptoms:** Many tasks accumulating in `AI_Employee_Vault/Retry_Queue/`.

**Solution:**
1. Check queue statistics
2. Process ready tasks: `process_retry_queue(actor)`
3. Clear stale tasks if needed
4. Investigate failure patterns

### Exponential Delay Too Long

**Symptoms:** Delays growing to maximum cap frequently.

**Solution:**
1. Lower `max_delay` in config
2. Reduce `exponential_base`
3. Check if failures are permanent (shouldn't retry)

---

## Performance Considerations

- **Jitter prevents thundering herd:** Multiple clients won't retry simultaneously
- **Circuit breaker fails fast:** Saves resources when service is down
- **Deferred retry reduces load:** Spreads retry attempts over time
- **Singleton pattern:** Shared state across components

---

## File Locations

| File | Description |
|------|-------------|
| `utils/retry_handler.py` | Core retry system implementation |
| `AI_Employee_Vault/Retry_Queue/` | Deferred retry task storage |
| `AI_Employee_Vault/Logs/audit_*.json` | Retry audit logs |

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-02-25 | Initial implementation |

---

*This document is part of the Gold Tier Error Recovery System.*
*Personal AI Employee Hackathon*
