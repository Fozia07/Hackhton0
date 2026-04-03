# Watchdog & Auto-Recovery System Skill

## Skill: watchdog-system

**Tier:** Gold
**Component:** Phase 1, Step 3
**Version:** 1.0.0
**Status:** Implemented

---

## Overview

Enterprise-grade Watchdog System that continuously monitors all AI Employee agents, detects failures, and automatically recovers crashed or hung processes. Ensures 24/7 autonomous operation with minimal human intervention.

---

## Monitored Agents

| Agent | Script | Priority |
|-------|--------|----------|
| AI Employee Runner | `scripts/run_ai_employee.py` | Critical |
| Agent Executor | `agent_executor.py` | Critical |
| Filesystem Watcher | `filesystem_watcher.py` | High |
| Plan Creator | `scripts/plan_creator.py` | Medium |
| LinkedIn Poster | `scripts/linkedin_poster.py` | Medium |
| CEO Briefing Generator | `scripts/ceo_briefing_generator.py` | Low |
| Email Server | `mcp_servers/email_server.py` | Medium |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    WATCHDOG SYSTEM                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  Heartbeat   │  │   Process    │  │   Resource   │          │
│  │   System     │  │   Monitor    │  │    Guard     │          │
│  │  (10s beat)  │  │ (crash/hung) │  │  (CPU/RAM)   │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
│         │                 │                 │                   │
│         └────────────┬────┴────────────────┘                   │
│                      │                                          │
│              ┌───────▼───────┐                                  │
│              │   Watchdog    │                                  │
│              │  Controller   │                                  │
│              └───────┬───────┘                                  │
│                      │                                          │
│         ┌────────────┼────────────┐                            │
│         │            │            │                             │
│  ┌──────▼──────┐ ┌───▼────┐ ┌────▼─────┐                       │
│  │ Auto Restart│ │Incident│ │ Safe     │                       │
│  │   Engine    │ │ Logger │ │ Mode     │                       │
│  └─────────────┘ └────────┘ └──────────┘                       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Components

### 1. Heartbeat System (`utils/heartbeat.py`)

**Purpose:** Track agent liveness via periodic heartbeats.

**Heartbeat Data:**
```json
{
  "agent": "agent_executor",
  "pid": 1234,
  "timestamp": "2026-02-25T10:00:00",
  "status": "running",
  "current_task": "processing_email_001",
  "cpu_percent": 23.1,
  "memory_percent": 41.3,
  "memory_mb": 156.2,
  "uptime_seconds": 3600,
  "tasks_completed": 45,
  "errors_count": 2,
  "last_error": null
}
```

**Thresholds:**
| Condition | Threshold | Action |
|-----------|-----------|--------|
| Healthy | < 30s since heartbeat | None |
| Warning | 30-60s since heartbeat | Log warning |
| Stale | 60-120s since heartbeat | Alert |
| Hung | > 120s since heartbeat | Force restart |
| Dead | > 300s since heartbeat | Full restart |

**Integration:**
- Each agent imports `HeartbeatWriter`
- Writes heartbeat every 10 seconds
- Stores in `AI_Employee_Vault/Watchdog/heartbeats.json`

---

### 2. Process Monitor (`utils/process_monitor.py`)

**Purpose:** Detect process anomalies.

**Detects:**
| Issue | Detection Method | Response |
|-------|------------------|----------|
| Crash | Process not running | Restart |
| Hung | No output > 120s | Kill + Restart |
| Zombie | Defunct process state | Clean + Restart |
| Infinite Loop | CPU 100% + no progress | Kill + Restart |
| Memory Leak | RAM growing unbounded | Restart |

**Process States:**
```
RUNNING → HEALTHY
NOT_FOUND → CRASHED
ZOMBIE → ZOMBIE
SLEEPING (long) → POSSIBLY_HUNG
HIGH_CPU (sustained) → INFINITE_LOOP
```

---

### 3. Resource Guard (`utils/resource_guard.py`)

**Purpose:** Monitor system resources and prevent overload.

**Thresholds:**
| Resource | Warning | Throttle | Emergency |
|----------|---------|----------|-----------|
| CPU | 70% | 85% | 95% |
| RAM | 65% | 80% | 90% |
| Disk | 80% | 90% | 95% |

**Actions:**
| Level | Action |
|-------|--------|
| Warning | Log + Alert |
| Throttle | Pause new tasks, slow processing |
| Emergency | Enter Safe Mode |

**Throttling Strategy:**
- Increase task delay intervals
- Pause non-critical agents
- Queue tasks instead of processing

---

### 4. Auto Restart Engine (`utils/auto_restart.py`)

**Purpose:** Safely restart failed processes.

**Restart Sequence:**
```
1. Graceful shutdown (SIGTERM, 10s timeout)
2. Force kill if needed (SIGKILL)
3. Wait cooldown period
4. Start new process
5. Verify heartbeat received
6. Log incident
```

**Backoff Strategy:**
| Restart # | Delay |
|-----------|-------|
| 1st | 5 seconds |
| 2nd | 15 seconds |
| 3rd | 30 seconds |
| 4th | 60 seconds |
| 5th+ | 120 seconds |

**Circuit Breaker:**
- Max 5 restarts per 10 minutes
- If exceeded → Enter Safe Mode

---

### 5. Incident Logger (`utils/incident_logger.py`)

**Purpose:** Track all watchdog events.

**Incident Format:**
```json
{
  "id": "INC_20260225_100000_001",
  "timestamp": "2026-02-25T10:00:00",
  "event": "process_restart",
  "severity": "high",
  "process": "agent_executor",
  "pid": 1234,
  "reason": "heartbeat_timeout",
  "details": {
    "last_heartbeat": "2026-02-25T09:58:00",
    "seconds_since": 120
  },
  "action": "restart",
  "result": "success",
  "new_pid": 5678
}
```

**Event Types:**
- `process_crash`
- `process_hung`
- `process_restart`
- `resource_warning`
- `resource_throttle`
- `safe_mode_enter`
- `safe_mode_exit`
- `heartbeat_stale`
- `heartbeat_recovered`

**Storage:**
- `AI_Employee_Vault/Watchdog/incidents.json`
- Integrates with `audit_logger`

---

### 6. Safe Mode (`utils/watchdog.py`)

**Purpose:** Emergency state to prevent cascading failures.

**Triggers:**
| Condition | Threshold |
|-----------|-----------|
| Rapid crashes | > 3 crashes in 10 minutes |
| Restart loop | > 5 restarts in 30 minutes |
| Memory critical | > 90% RAM usage |
| CPU critical | > 95% CPU sustained |

**Safe Mode Actions:**
1. Pause all task processing
2. Stop non-critical agents
3. Keep only: Watchdog + Audit Logger
4. Write alert to `AI_Employee_Vault/Watchdog/SAFE_MODE_ACTIVE`
5. Log to audit system
6. Wait for manual intervention OR auto-recover after 15 min

**Recovery:**
- Automatic after 15 minutes if resources normalized
- Manual: Delete `SAFE_MODE_ACTIVE` file
- Gradual restart of agents

---

### 7. System Daemon (`scripts/system_watchdog.py`)

**Purpose:** Main watchdog process that runs continuously.

**Execution:**
```bash
# Normal mode
python3 scripts/system_watchdog.py

# Debug mode (verbose logging)
python3 scripts/system_watchdog.py --debug

# Dry run (no actual restarts)
python3 scripts/system_watchdog.py --dry-run

# Single check (run once and exit)
python3 scripts/system_watchdog.py --once
```

**Main Loop (every 10 seconds):**
```
1. Collect all heartbeats
2. Check process states
3. Check resource usage
4. Identify unhealthy agents
5. Execute recovery actions
6. Log incidents
7. Update health.json
8. Check safe mode triggers
9. Sleep 10 seconds
```

---

## File Structure

```
utils/
├── heartbeat.py          # Heartbeat system
├── process_monitor.py    # Process health checks
├── resource_guard.py     # CPU/RAM monitoring
├── incident_logger.py    # Incident tracking
├── auto_restart.py       # Safe restart manager
└── watchdog.py           # Main watchdog controller

scripts/
└── system_watchdog.py    # Standalone daemon

AI_Employee_Vault/
└── Watchdog/
    ├── heartbeats.json   # Current heartbeats
    ├── health.json       # System health summary
    ├── incidents.json    # Incident history
    ├── restarts.json     # Restart history
    ├── metrics.json      # Performance metrics
    └── SAFE_MODE_ACTIVE  # Safe mode flag (when active)
```

---

## Agent Integration

Each agent must integrate heartbeat:

```python
from utils.heartbeat import get_heartbeat_writer, AgentStatus

# Initialize at startup
heartbeat = get_heartbeat_writer("agent_name")
heartbeat.set_status(AgentStatus.RUNNING)

# During task processing
heartbeat.set_task("task_description")
# ... do work ...
heartbeat.task_completed()

# On error
heartbeat.record_error("error message")

# On shutdown
heartbeat.stop()
```

**Files to Update:**
- `agent_executor.py`
- `scripts/run_ai_employee.py`
- `filesystem_watcher.py`
- `scripts/plan_creator.py`
- `scripts/linkedin_poster.py`
- `scripts/ceo_briefing_generator.py`
- `mcp_servers/email_server.py`

---

## Configuration

**Environment Variables:**
| Variable | Default | Description |
|----------|---------|-------------|
| WATCHDOG_INTERVAL | 10 | Check interval (seconds) |
| HEARTBEAT_INTERVAL | 10 | Heartbeat write interval |
| STALE_THRESHOLD | 60 | Seconds before stale |
| HUNG_THRESHOLD | 120 | Seconds before hung |
| CPU_THROTTLE | 85 | CPU % to trigger throttle |
| RAM_THROTTLE | 80 | RAM % to trigger throttle |
| SAFE_MODE_CRASHES | 3 | Crashes to trigger safe mode |
| SAFE_MODE_WINDOW | 600 | Window for crash count (seconds) |

---

## Monitoring Dashboard

**Health Summary (`health.json`):**
```json
{
  "timestamp": "2026-02-25T10:00:00",
  "system_status": "healthy",
  "safe_mode": false,
  "agents": {
    "agent_executor": {
      "status": "healthy",
      "pid": 1234,
      "uptime": "2h 30m",
      "last_heartbeat": "5s ago"
    }
  },
  "resources": {
    "cpu_percent": 45.2,
    "memory_percent": 62.1,
    "disk_percent": 55.0
  },
  "incidents_24h": 3,
  "restarts_24h": 1
}
```

---

## Production Requirements

- **Thread-safe:** All operations use locks
- **Cross-platform:** Windows + Linux + WSL compatible
- **Minimal overhead:** < 1% CPU usage
- **Fault tolerant:** Watchdog itself must not crash
- **Graceful shutdown:** Handle SIGTERM/SIGINT
- **Atomic writes:** No corrupted JSON files
- **Structured logging:** Full audit trail

---

## Testing Checklist

- [x] Heartbeat writing/reading works
- [x] Stale heartbeat detection works
- [x] Process crash detection works
- [x] Hung process detection works
- [x] Auto restart works
- [x] Backoff timing correct
- [x] Resource monitoring works
- [x] Throttling activates correctly
- [x] Safe mode triggers correctly
- [x] Safe mode recovery works
- [x] Incident logging works
- [x] Audit integration works
- [x] Cross-platform tested
- [x] Daemon runs continuously
- [x] Clean shutdown works

---

## Related Skills

- `error-recovery.md` - Retry system integration
- `audit-logging.md` - Incident logging integration
- `ai_employee_runner.md` - Primary monitored process

---

## Documentation

- `docs/WATCHDOG_SYSTEM.md` - Full technical documentation

---

*Gold Tier - Watchdog & Auto-Recovery System*
*Personal AI Employee Hackathon*
