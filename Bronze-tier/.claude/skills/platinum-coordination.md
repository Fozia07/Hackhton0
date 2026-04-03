# Platinum Tier - Multi-Agent Coordination Skill

## Skill: platinum-coordination

**Tier:** Platinum
**Version:** 1.0.0
**Status:** Implemented

---

## Overview

Enterprise-grade multi-agent coordination system enabling Cloud and Local agents to work together on a shared vault without conflicts. Implements claim-by-move task ownership, work-zone specialization, and signal-based communication.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│              PLATINUM MULTI-AGENT COORDINATION                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   ┌─────────────────┐                   ┌─────────────────┐         │
│   │   CLOUD AGENT   │◄─── Git Sync ────►│   LOCAL AGENT   │         │
│   │   (24/7 VM)     │                   │   (Laptop)      │         │
│   └────────┬────────┘                   └────────┬────────┘         │
│            │                                     │                   │
│   ┌────────┴────────┐                   ┌────────┴────────┐         │
│   │ Owned Zones:    │                   │ Owned Zones:    │         │
│   │ - email_triage  │                   │ - email_send    │         │
│   │ - social_draft  │                   │ - social_post   │         │
│   │ - odoo_read     │                   │ - approvals     │         │
│   └────────┬────────┘                   │ - payments      │         │
│            │                            │ - whatsapp      │         │
│            │                            │ - dashboard     │         │
│            │                            └────────┬────────┘         │
│            │                                     │                   │
│            └──────────────┬──────────────────────┘                  │
│                           │                                          │
│                           ▼                                          │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │                    SHARED VAULT                              │   │
│   │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │   │
│   │  │In_Progress/ │  │  Updates/   │  │     Signals/        │  │   │
│   │  │├── cloud/   │  │             │  │                     │  │   │
│   │  │└── local/   │  │             │  │                     │  │   │
│   │  └─────────────┘  └─────────────┘  └─────────────────────┘  │   │
│   └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Core Concepts

### 1. Claim-by-Move Rule

Prevents double-work by requiring agents to physically move tasks to claim ownership.

```
┌─────────────────────────────────────────────────────────────────┐
│                    CLAIM-BY-MOVE FLOW                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   /Needs_Action/task.md                                         │
│          │                                                       │
│          │  ← Cloud agent sees task first                       │
│          ▼                                                       │
│   MOVE to /In_Progress/cloud/task.md  (CLAIMED!)               │
│          │                                                       │
│          │  ← Local agent checks, file is gone                  │
│          │  ← Local skips this task                             │
│          ▼                                                       │
│   Cloud processes task                                          │
│          │                                                       │
│          ▼                                                       │
│   MOVE to /Pending_Approval/  or  /Done/                        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 2. Work-Zone Ownership

Each agent owns specific work zones:

| Zone | Cloud Agent | Local Agent |
|------|-------------|-------------|
| `email_triage` | **Owns** | Read-only |
| `email_send` | Draft-only | **Owns** |
| `social_draft` | **Owns** | Read-only |
| `social_post` | No access | **Owns** |
| `approvals` | No access | **Owns** |
| `whatsapp` | No access | **Owns** |
| `payments` | No access | **Owns** |
| `odoo_read` | Full | Full |
| `odoo_write` | No access | **Owns** |
| `dashboard` | No access | **Owns** |

### 3. Single-Writer Dashboard Rule

Only the Local agent writes to `Dashboard.md`. Cloud agent writes updates to `/Updates/` folder.

```
Cloud Agent                          Local Agent
    │                                     │
    │ Creates metrics                     │
    ▼                                     │
/Updates/dashboard_xxx.json              │
    │                                     │
    └─────── Git Sync ────────────────────┘
                                          │
                                          ▼
                              Reads /Updates/*.json
                                          │
                                          ▼
                              Merges into Dashboard.md
                                          │
                                          ▼
                              Moves update to /processed/
```

---

## Components

### 1. Claim Manager (`utils/claim_manager.py`)

Handles atomic task claiming with file locking.

```python
from utils.claim_manager import get_claim_manager, ClaimStatus

# Initialize for this agent
manager = get_claim_manager("local")

# Claim a task
status, msg = manager.claim_task("task.md", "email")
if status == ClaimStatus.SUCCESS:
    # Process task
    pass

# Release when done
manager.release_task("task.md", "done")
```

### 2. Agent Coordinator (`utils/agent_coordinator.py`)

Manages signals, updates, and work-zone permissions.

```python
from utils.agent_coordinator import get_coordinator

coordinator = get_coordinator("local")

# Check permissions
permission = coordinator.can_access_zone("payments")

# Send signal to other agent
coordinator.send_signal("approval_needed", "cloud", {"task": "invoice.md"})

# Check for signals
signals = coordinator.get_pending_signals()

# Update heartbeat
coordinator.update_heartbeat()
```

### 3. Platinum Orchestrator (`scripts/platinum_orchestrator.py`)

Main orchestration loop with claim-by-move integration.

```bash
# Run as Local agent (default)
python3 scripts/platinum_orchestrator.py

# Run as Cloud agent
python3 scripts/platinum_orchestrator.py --agent cloud

# Single cycle
python3 scripts/platinum_orchestrator.py --once

# Dry run
python3 scripts/platinum_orchestrator.py --dry-run

# Check status
python3 scripts/platinum_orchestrator.py --status
```

---

## Folder Structure

```
AI_Employee_Vault/
├── In_Progress/              # Active tasks (claimed)
│   ├── cloud/                # Cloud agent's workspace
│   │   └── .gitkeep
│   └── local/                # Local agent's workspace
│       └── .gitkeep
├── Updates/                  # Cloud → Local updates
│   ├── dashboard_xxx.json    # Dashboard metrics
│   └── processed/            # Processed updates
├── Signals/                  # Inter-agent signals
│   ├── heartbeat_cloud.json  # Cloud agent heartbeat
│   ├── heartbeat_local.json  # Local agent heartbeat
│   └── approval_needed_xxx.json
├── Needs_Action/             # Unclaimed tasks
├── Pending_Approval/         # Drafts awaiting approval
├── Approved/                 # Approved for action
└── Done/                     # Completed tasks

config/
├── agent_config.json         # Local agent config
├── agent_config.cloud.json   # Cloud agent config
└── work_zones.json           # Work zone definitions
```

---

## Configuration Files

### agent_config.json (Local)

```json
{
  "agent_id": "local",
  "agent_type": "local",
  "owned_zones": ["email_send", "social_post", "approvals", "payments"],
  "permissions": {
    "can_send_email": true,
    "can_approve": true
  }
}
```

### agent_config.cloud.json (Cloud)

```json
{
  "agent_id": "cloud",
  "agent_type": "cloud",
  "owned_zones": ["email_triage", "social_draft"],
  "draft_only_zones": ["email_send", "social_post"],
  "permissions": {
    "can_send_email": false,
    "can_draft_email": true
  }
}
```

### work_zones.json

```json
{
  "zones": {
    "email_triage": {
      "cloud_permission": "full_access",
      "local_permission": "read_only",
      "owner": "cloud"
    },
    "email_send": {
      "cloud_permission": "draft_only",
      "local_permission": "full_access",
      "owner": "local",
      "requires_approval": true
    }
  }
}
```

---

## CLI Commands

```bash
# Claim Manager
python3 -m utils.claim_manager --agent local --action status
python3 -m utils.claim_manager --agent local --action claim --task task.md
python3 -m utils.claim_manager --agent local --action release --task task.md

# Agent Coordinator
python3 -m utils.agent_coordinator --agent local --action status
python3 -m utils.agent_coordinator --agent local --action heartbeat
python3 -m utils.agent_coordinator --agent local --action signal --signal-type test --to cloud

# Platinum Orchestrator
python3 scripts/platinum_orchestrator.py --status
python3 scripts/platinum_orchestrator.py --once --verbose
python3 scripts/platinum_orchestrator.py --agent cloud --dry-run
```

---

## Signal Types

| Signal Type | From | To | Purpose |
|-------------|------|----|---------|
| `approval_needed` | Cloud | Local | Draft ready for approval |
| `task_complete` | Any | Any | Task finished |
| `urgent_task` | Any | Any | High priority task |
| `sync_request` | Any | Any | Request vault sync |
| `heartbeat` | Any | Any | Health check |

---

## Security Rules

1. **Secrets Never Sync**: `.env`, tokens, WhatsApp sessions excluded from Git
2. **Cloud is Draft-Only**: Cloud cannot execute final actions
3. **Local Owns Approvals**: All approvals require Local agent
4. **Payments Local Only**: Financial actions only on Local

---

## Testing

```bash
# Test claim-by-move
python3 -c "
from utils.claim_manager import get_claim_manager

# Simulate Cloud claiming
cloud = get_claim_manager('cloud')
status, msg = cloud.claim_task('test.md')
print(f'Cloud claim: {status.value}')

# Simulate Local trying to claim same task
local = get_claim_manager('local')
status, msg = local.claim_task('test.md')
print(f'Local claim: {status.value}')  # Should be ALREADY_CLAIMED
"

# Test full orchestrator
python3 scripts/platinum_orchestrator.py --once --dry-run --verbose
```

---

## Vault Sync (Phase 3)

### Overview

Git-based synchronization keeps Cloud and Local agents in sync:

```
┌─────────────────┐         Git Repo          ┌─────────────────┐
│   Cloud Agent   │◄──────(GitHub)───────────►│   Local Agent   │
│   sync every    │                            │   sync every    │
│     60s         │                            │      30s        │
└─────────────────┘                            └─────────────────┘
```

### Sync Script (`scripts/sync_vault.py`)

```bash
# Single sync cycle
python3 scripts/sync_vault.py --once --agent-id local

# Continuous sync (30s interval)
python3 scripts/sync_vault.py --agent-id local --interval 30

# Initialize vault as git repo
python3 scripts/sync_vault.py --init --remote git@github.com:user/vault.git

# Check status
python3 scripts/sync_vault.py --status
```

### Sync Cycle

1. **Pull** - Get latest from remote (stash local changes first)
2. **Commit** - Stage and commit local changes with timestamp
3. **Push** - Push to remote (retry on conflict)

### What Gets Synced

| Folder | Synced? | Notes |
|--------|---------|-------|
| `Needs_Action/` | Yes | New tasks |
| `Pending_Approval/` | Yes | Drafts for review |
| `Approved/` | Yes | Ready to execute |
| `Done/` | Yes | Completed tasks |
| `Updates/` | Yes | Agent communication |
| `Signals/` | Yes | Inter-agent signals |
| `Logs/` | No | Local only |
| `.env` | No | Never sync secrets! |

### Commit Message Format

```
[local] Auto-sync: 3 file(s) (2024-01-15 14:30:00)
[cloud] Auto-sync: 1 file(s) (2024-01-15 14:30:30)
```

---

## Related Skills

- `watchdog-system.md` - Process monitoring
- `error-recovery.md` - Retry handling
- `audit-logging.md` - Action logging

---

*Platinum Tier - Multi-Agent Coordination*
*AI Employee Hackathon*
