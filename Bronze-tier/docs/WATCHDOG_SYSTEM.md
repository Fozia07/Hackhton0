# Watchdog & Auto-Recovery System

**Gold Tier Component | Version 1.0.0**

Enterprise-grade watchdog system for the AI Employee platform providing continuous monitoring, automatic recovery, and system health management.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Components](#components)
4. [Quick Start](#quick-start)
5. [Configuration](#configuration)
6. [Monitoring Features](#monitoring-features)
7. [Auto-Recovery](#auto-recovery)
8. [Safe Mode](#safe-mode)
9. [API Reference](#api-reference)
10. [Integration Guide](#integration-guide)
11. [Troubleshooting](#troubleshooting)

---

## Overview

The Watchdog System provides:

- **Continuous Monitoring**: Real-time health checks every 10 seconds
- **Heartbeat System**: Agents report status, CPU, memory usage
- **Process Monitoring**: Detect crashes, hangs, zombies, runaway processes
- **Resource Guard**: CPU/RAM monitoring with automatic throttling
- **Auto-Recovery**: Restart failed processes with exponential backoff
- **Circuit Breaker**: Prevent restart loops with intelligent protection
- **Safe Mode**: Emergency protection when system is overwhelmed
- **Incident Logging**: Full audit trail of all system events

### Monitored Processes

| Process | Description | Critical |
|---------|-------------|----------|
| `run_ai_employee` | Main task processor | Yes |
| `agent_executor` | Task execution engine | Yes |
| `filesystem_watcher` | Inbox monitoring | Yes |
| `plan_creator` | Plan generation | No |
| `linkedin_poster` | LinkedIn integration | No |
| `ceo_briefing_generator` | CEO briefings | No |
| `email_server` | Email MCP server | No |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    WATCHDOG CONTROLLER                          │
│                    (utils/watchdog.py)                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │   Heartbeat  │  │   Process    │  │   Resource Guard     │  │
│  │   Manager    │  │   Monitor    │  │   (CPU/RAM/Disk)     │  │
│  │              │  │              │  │                      │  │
│  │  heartbeat.py│  │process_mon.py│  │  resource_guard.py   │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐                            │
│  │ Auto Restart │  │  Incident    │                            │
│  │   Engine     │  │  Logger      │                            │
│  │              │  │              │                            │
│  │auto_restart.py│ │incident_log.py│                           │
│  └──────────────┘  └──────────────┘                            │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                    SYSTEM DAEMON                                │
│               (scripts/system_watchdog.py)                      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     MONITORED AGENTS                            │
│                                                                 │
│   run_ai_employee.py    agent_executor.py    filesystem_watcher │
│   plan_creator.py       linkedin_poster.py   ceo_briefing.py    │
│                                                                 │
│   [Each agent writes heartbeat every 10 seconds]                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   AI_Employee_Vault/Watchdog/                   │
│                                                                 │
│   heartbeats.json    health.json    incidents.json              │
│   restarts.json      metrics.json   SAFE_MODE_ACTIVE            │
└─────────────────────────────────────────────────────────────────┘
```

---

## Components

### 1. Heartbeat System (`utils/heartbeat.py`)

Agents report their health status every 10 seconds.

**Heartbeat Data:**
```json
{
  "agent": "agent_executor",
  "pid": 1234,
  "timestamp": "2024-01-15T10:30:00.000Z",
  "status": "running",
  "current_task": "processing:task_001.md",
  "cpu": 23.1,
  "memory": 41.3,
  "uptime_seconds": 3600
}
```

**Health Levels:**
- `HEALTHY`: Heartbeat < 30s old
- `WARNING`: Heartbeat 30-45s old
- `STALE`: Heartbeat 45-60s old
- `HUNG`: Heartbeat 60-120s old
- `DEAD`: Heartbeat > 120s old

### 2. Process Monitor (`utils/process_monitor.py`)

Detects process anomalies:

| Anomaly | Detection | Action |
|---------|-----------|--------|
| Crashed | Process not found | Restart |
| Hung | Low CPU for >120s | Kill & Restart |
| Zombie | Zombie state | Kill & Restart |
| Runaway | CPU >95% sustained | Kill & Restart |
| Memory Leak | Unbounded growth | Warning |

### 3. Resource Guard (`utils/resource_guard.py`)

System resource monitoring and throttling:

| Level | CPU | RAM | Action |
|-------|-----|-----|--------|
| Normal | <70% | <65% | Normal operation |
| Warning | 70-75% | 65-70% | Log warning |
| Throttle | 75-85% | 70-80% | Slow down tasks |
| Emergency | 85-95% | 80-90% | Pause non-critical |
| Critical | >95% | >90% | Safe mode |

### 4. Auto Restart Engine (`utils/auto_restart.py`)

Intelligent process recovery:

**Backoff Strategy:**
- Attempt 1: 5s delay
- Attempt 2: 15s delay
- Attempt 3: 30s delay
- Attempt 4: 60s delay
- Attempt 5: 120s delay
- Maximum: 10 minutes

**Circuit Breaker:**
- Opens after 5 failures in 10 minutes
- Prevents restart loops
- Auto-resets after 5 minutes

### 5. Incident Logger (`utils/incident_logger.py`)

Full audit trail of all events:

**Incident Types:**
- `PROCESS_CRASH` - Process terminated unexpectedly
- `PROCESS_HUNG` - Process not responding
- `PROCESS_RESTART` - Process was restarted
- `HEARTBEAT_STALE` - Heartbeat timeout
- `RESOURCE_WARNING` - High resource usage
- `SAFE_MODE_ENTER/EXIT` - Safe mode state changes
- `CIRCUIT_BREAKER_OPEN/CLOSE` - Circuit breaker events

---

## Quick Start

### Starting the Watchdog Daemon

```bash
# Normal operation
python3 scripts/system_watchdog.py

# Debug mode (verbose output)
python3 scripts/system_watchdog.py --debug

# Dry run (no actual restarts)
python3 scripts/system_watchdog.py --dry-run

# Single scan and exit
python3 scripts/system_watchdog.py --once

# Check status
python3 scripts/system_watchdog.py --status
```

### Manual Safe Mode Control

```bash
# Enter safe mode
python3 scripts/system_watchdog.py --safe-mode

# Exit safe mode
python3 scripts/system_watchdog.py --exit-safe
```

---

## Configuration

### Watchdog Configuration

```python
from utils.watchdog import WatchdogConfig, SafeModeConfig

config = WatchdogConfig(
    scan_interval=10.0,              # Scan every 10 seconds
    heartbeat_timeout=60.0,          # 60s heartbeat timeout
    hung_threshold=120.0,            # 120s hung detection
    process_check_interval=30.0,     # Process check every 30s
    resource_check_interval=15.0,    # Resource check every 15s
    health_output_interval=60.0,     # Health output every 60s

    safe_mode=SafeModeConfig(
        crash_threshold=3,           # 3 crashes triggers safe mode
        crash_window_seconds=600,    # Within 10 minutes
        restart_threshold=5,         # 5 restarts triggers safe mode
        restart_window_seconds=1800, # Within 30 minutes
        memory_threshold=90.0,       # 90% memory triggers safe mode
        cpu_threshold=95.0,          # 95% CPU triggers safe mode
        recovery_timeout_seconds=900,# 15 min safe mode recovery
        auto_recover=True            # Auto-exit safe mode
    )
)
```

### Process Configuration

```python
from utils.auto_restart import ProcessConfig

config = ProcessConfig(
    name="agent_executor",
    command=["python3", "agent_executor.py"],
    working_dir="/path/to/project",
    graceful_timeout=10.0,     # 10s graceful shutdown
    terminate_timeout=5.0,     # 5s force terminate
    startup_timeout=30.0,      # 30s startup verification
    priority=1,                # 1=highest priority
    critical=True,             # Run even in safe mode
    max_restarts=5,            # Max 5 restarts
    restart_window_seconds=600 # Per 10 minute window
)
```

---

## Monitoring Features

### System Health Dashboard

Access via `AI_Employee_Vault/Watchdog/health.json`:

```json
{
  "timestamp": "2024-01-15T10:30:00.000Z",
  "state": "running",
  "uptime_seconds": 86400,
  "processes_healthy": 6,
  "processes_warning": 1,
  "processes_critical": 0,
  "processes_total": 7,
  "cpu_percent": 45.2,
  "memory_percent": 62.1,
  "disk_percent": 55.0,
  "resource_level": "normal",
  "throttle_factor": 1.0,
  "safe_mode_active": false,
  "safe_mode_reason": null,
  "open_circuits": [],
  "recent_incidents": 2,
  "last_scan": "2024-01-15T10:29:50.000Z"
}
```

### Incident History

View in `AI_Employee_Vault/Watchdog/incidents.json`:

```json
{
  "timestamp": "2024-01-15T10:25:00.000Z",
  "event": "process_restart",
  "process": "agent_executor",
  "reason": "heartbeat_timeout",
  "action": "restart",
  "result": "success",
  "details": {
    "old_pid": 1234,
    "new_pid": 1235,
    "attempt": 1,
    "duration_ms": 2500
  }
}
```

---

## Auto-Recovery

### Recovery Flow

```
1. Anomaly Detected
       │
       ▼
2. Log Incident
       │
       ▼
3. Check Circuit Breaker ──────┐
       │                       │
       ▼ (closed)              ▼ (open)
4. Calculate Backoff      Skip Recovery
       │                       │
       ▼                       ▼
5. Wait Backoff           Log Warning
       │
       ▼
6. Stop Process (graceful → force)
       │
       ▼
7. Start Process
       │
       ▼
8. Verify Startup
       │
       ▼
9. Record Success/Failure
```

### Recovery Methods

**Graceful Shutdown:**
1. Send SIGTERM
2. Wait 10 seconds
3. Check if stopped

**Force Kill:**
1. Send SIGKILL
2. Wait 5 seconds
3. Verify termination

**Restart Verification:**
1. Start new process
2. Wait for startup (30s max)
3. Verify PID exists
4. Optional health check callback

---

## Safe Mode

### Triggers

Safe mode activates when:

| Trigger | Threshold |
|---------|-----------|
| Crashes | 3+ in 10 minutes |
| Restarts | 5+ in 30 minutes |
| Memory | >90% usage |
| CPU | >95% sustained |
| Circuit Breakers | 3+ open |

### Behavior

When safe mode is active:

1. **Non-critical processes paused** - Only critical processes run
2. **No new tasks started** - Existing tasks complete
3. **Watchdog + Logging continue** - Monitoring stays active
4. **Auto-recovery attempts** - After 15 minutes

### Exit Conditions

Safe mode exits when:

1. **Manual exit**: `--exit-safe` command
2. **Auto-recovery**: After 15 minutes if resources normalized
3. **Resources stable**: CPU <85%, Memory <80%

### Safe Mode Flag

File: `AI_Employee_Vault/Watchdog/SAFE_MODE_ACTIVE`

```json
{
  "entered_at": "2024-01-15T10:00:00.000Z",
  "reason": "crash_threshold"
}
```

---

## API Reference

### WatchdogController

```python
from utils.watchdog import get_watchdog

watchdog = get_watchdog()

# Start monitoring
watchdog.start()

# Stop monitoring
watchdog.stop()

# Get system health
health = watchdog.get_system_health()

# Get process health
proc_health = watchdog.get_process_health("agent_executor")

# Enter/exit safe mode
watchdog.enter_safe_mode(SafeModeReason.MANUAL)
watchdog.exit_safe_mode()

# Check state
state = watchdog.get_state()
is_safe = watchdog.is_safe_mode()

# Single scan
health = watchdog.scan_once()
```

### HeartbeatWriter

```python
from utils.heartbeat import HeartbeatWriter

# Initialize
heartbeat = HeartbeatWriter("my_agent")

# Start background heartbeat (every 10s)
heartbeat.start()

# Update current task
heartbeat.update_task("processing:file.md")

# Stop heartbeat
heartbeat.stop()
```

### AutoRestartEngine

```python
from utils.auto_restart import get_restart_engine, ProcessConfig

engine = get_restart_engine()

# Configure process
engine.configure_process(ProcessConfig(
    name="my_process",
    command=["python3", "my_script.py"]
))

# Restart a process
result = engine.restart_process("my_process", current_pid=1234, reason="manual")

# Check circuit breaker
is_open = engine.is_circuit_open("my_process")

# Reset circuit
engine.reset_circuit("my_process")

# Get statistics
stats = engine.get_stats()
```

---

## Integration Guide

### Adding Heartbeat to a New Agent

```python
#!/usr/bin/env python3
"""Example agent with heartbeat integration."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.heartbeat import HeartbeatWriter

# Initialize heartbeat
heartbeat = HeartbeatWriter("my_agent")

def main():
    # Start heartbeat
    heartbeat.start()
    heartbeat.update_task("initializing")

    try:
        while True:
            # Update task
            heartbeat.update_task("processing:current_task")

            # Do work...
            process_task()

            # Update on completion
            heartbeat.update_task("idle")

    except KeyboardInterrupt:
        pass
    finally:
        # Stop heartbeat
        heartbeat.update_task("stopped")
        heartbeat.stop()

if __name__ == "__main__":
    main()
```

### Registering with Watchdog

```python
from utils.watchdog import get_watchdog
from utils.auto_restart import ProcessConfig
import os

watchdog = get_watchdog()

# Register process
watchdog.register_process(
    name="my_agent",
    pid=os.getpid(),
    config=ProcessConfig(
        name="my_agent",
        command=["python3", "my_agent.py"],
        critical=False,
        priority=3
    )
)
```

---

## Troubleshooting

### Common Issues

**Heartbeat Not Detected:**
```bash
# Check heartbeats file
cat AI_Employee_Vault/Watchdog/heartbeats.json

# Verify agent is writing heartbeat
ps aux | grep agent_executor
```

**Safe Mode Won't Exit:**
```bash
# Manual exit
python3 scripts/system_watchdog.py --exit-safe

# Remove flag file
rm AI_Employee_Vault/Watchdog/SAFE_MODE_ACTIVE
```

**Circuit Breaker Stuck Open:**
```python
from utils.auto_restart import reset_circuit
reset_circuit("agent_executor")
```

**High Memory Usage:**
```bash
# Check resource status
python3 scripts/system_watchdog.py --status

# View resource history
cat AI_Employee_Vault/Watchdog/metrics.json
```

### Log Files

| File | Purpose |
|------|---------|
| `Watchdog/health.json` | Current system health |
| `Watchdog/incidents.json` | Incident history |
| `Watchdog/restarts.json` | Restart history |
| `Watchdog/heartbeats.json` | Agent heartbeats |
| `Watchdog/metrics.json` | Resource metrics |
| `Logs/audit_log_*.json` | Full audit trail |

### Debug Mode

Run with `--debug` for verbose output:

```bash
python3 scripts/system_watchdog.py --debug
```

Output includes:
- Every heartbeat check
- Process state transitions
- Resource measurements
- Recovery attempts
- All incidents

---

## Production Deployment

### Systemd Service (Linux)

Create `/etc/systemd/system/ai-employee-watchdog.service`:

```ini
[Unit]
Description=AI Employee Watchdog System
After=network.target

[Service]
Type=simple
User=ai-employee
WorkingDirectory=/path/to/Bronze-tier
ExecStart=/usr/bin/python3 scripts/system_watchdog.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable ai-employee-watchdog
sudo systemctl start ai-employee-watchdog
```

### Windows Task Scheduler

Create scheduled task:
- Run: `python.exe scripts/system_watchdog.py`
- Trigger: At system startup
- Settings: Restart on failure

### Health Check Endpoint

The watchdog writes health status to `health.json` which can be monitored by external systems:

```bash
# Check via cURL
curl -s file:///path/to/AI_Employee_Vault/Watchdog/health.json | jq .state

# Alert if not running
if [ "$(cat health.json | jq -r .state)" != "running" ]; then
  echo "ALERT: Watchdog not running!"
fi
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2024-01 | Initial release |

---

*Part of the AI Employee Gold Tier System*
