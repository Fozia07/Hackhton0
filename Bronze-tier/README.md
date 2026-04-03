# Personal AI Employee - Bronze + Silver Tier

**Hackathon:** Personal AI Employee Hackathon 0
**Tier:** Bronze (Foundation) + Silver (Functional Assistant)
**Author:** Fozia Mustafa
**Date:** 2026-02-21

---

## Overview

This project implements both **Bronze** and **Silver** tiers for an autonomous AI Employee system. It provides a file-based task management workflow using an Obsidian vault, with automated task detection, AI-powered planning, human-in-the-loop approval, and external integrations.

**Concept:** A Digital FTE (Full-Time Equivalent) that manages tasks 24/7 using local-first, file-based automation.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                 SILVER TIER SYSTEM ARCHITECTURE                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐          │
│   │Gmail Watcher│   │FS Watcher   │   │LinkedIn Bot │          │
│   └──────┬──────┘   └──────┬──────┘   └──────┬──────┘          │
│          │                 │                 │                  │
│          └────────────────┼────────────────┘                   │
│                           ▼                                     │
│                    ┌─────────────┐                              │
│                    │    INBOX    │                              │
│                    │  /email     │                              │
│                    │  /linkedin  │                              │
│                    │  /general   │                              │
│                    └──────┬──────┘                              │
│                           ▼                                     │
│                    ┌─────────────┐                              │
│                    │NEEDS_ACTION │ ───► Plan Creator            │
│                    └──────┬──────┘            │                 │
│                           │                   ▼                 │
│                           │            ┌─────────────┐          │
│                           │            │   PLANS     │          │
│                           │            └─────────────┘          │
│                           ▼                                     │
│                  ┌─────────────────┐                            │
│                  │PENDING_APPROVAL │ ◄── Human Decision         │
│                  └────────┬────────┘                            │
│                           │                                     │
│            ┌──────────────┴──────────────┐                      │
│            ▼                             ▼                      │
│     ┌─────────────┐              ┌─────────────┐                │
│     │  APPROVED   │              │  REJECTED   │                │
│     └──────┬──────┘              └─────────────┘                │
│            │                                                    │
│            ▼                                                    │
│     ┌─────────────┐                                             │
│     │ MCP Server  │ ───► Email/LinkedIn Actions                 │
│     └──────┬──────┘                                             │
│            │                                                    │
│            ▼                                                    │
│     ┌─────────────┐                                             │
│     │    DONE     │ ───► Logs                                   │
│     └─────────────┘                                             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Folder Structure

```
Bronze-tier/
├── .claude/                        # Claude Code configuration
│   └── skills/                     # Agent skill definitions
│       ├── SKILLS_INDEX.md
│       ├── approval_workflow.md
│       ├── gmail_watcher.md
│       ├── linkedin_poster.md
│       ├── plan_creator.md
│       ├── email_sender.md
│       └── scheduler.md
├── AI_Employee_Vault/              # Obsidian Vault
│   ├── Inbox/
│   │   ├── email/                  # Email tasks (Silver)
│   │   ├── linkedin/               # LinkedIn tasks (Silver)
│   │   └── general/                # General tasks
│   ├── Needs_Action/
│   │   ├── email/
│   │   ├── linkedin/
│   │   └── general/
│   ├── Plans/                      # AI-generated plans (Silver)
│   ├── Pending_Approval/           # Human-in-the-loop (Silver)
│   ├── Approved/                   # Approved actions (Silver)
│   ├── Rejected/                   # Rejected actions (Silver)
│   ├── Done/                       # Completed tasks
│   ├── Logs/                       # Operation logs
│   ├── Schedules/                  # Cron schedules (Silver)
│   ├── Dashboard.md
│   ├── Company_Handbook.md
│   ├── Business_Goals.md
│   ├── Agent_Skills.md
│   └── AI_Task_Flow.md
├── watchers/                       # Watcher scripts (Silver)
│   ├── approval_watcher.py
│   └── gmail_watcher.py
├── scripts/                        # Utility scripts (Silver)
│   ├── plan_creator.py
│   ├── linkedin_poster.py
│   └── scheduler_manager.py
├── mcp_servers/                    # MCP servers (Silver)
│   ├── email_server.py
│   └── mcp_config.json
├── filesystem_watcher.py           # Bronze watcher
├── agent_executor.py               # Bronze executor
└── README.md
```

---

## Tier Completion Status

### Bronze Tier ✅ COMPLETE

| Requirement | Status |
|-------------|--------|
| Obsidian vault with Dashboard.md | ✅ |
| Company_Handbook.md | ✅ |
| One working Watcher script | ✅ |
| Basic folder structure | ✅ |
| Agent Skills defined | ✅ |

### Silver Tier ✅ COMPLETE

| Requirement | Status |
|-------------|--------|
| Two+ Watcher scripts (Gmail + Filesystem) | ✅ |
| LinkedIn automation (Playwright) | ✅ |
| Claude reasoning loop (Plan.md) | ✅ |
| MCP server for email | ✅ |
| Human-in-the-loop approval | ✅ |
| Cron scheduling | ✅ |
| Agent Skills implementation | ✅ |

---

## Setup Instructions

### Prerequisites

```bash
# Python 3.10+
python3 --version

# Optional: Install Playwright for LinkedIn
pip install playwright
playwright install chromium

# Optional: Install Gmail API libraries
pip install google-auth-oauthlib google-api-python-client
```

### Quick Start

```bash
cd Bronze-tier

# Start filesystem watcher
python3 filesystem_watcher.py

# In another terminal - start approval watcher
python3 watchers/approval_watcher.py

# Run plan creator
python3 scripts/plan_creator.py

# Test Gmail watcher (simulation mode)
python3 watchers/gmail_watcher.py --simulate
```

---

## Key Components

### Watchers
| Script | Purpose |
|--------|---------|
| `filesystem_watcher.py` | Monitor Inbox for new files |
| `watchers/gmail_watcher.py` | Monitor Gmail for emails |
| `watchers/approval_watcher.py` | Process approval decisions |

### Scripts
| Script | Purpose |
|--------|---------|
| `scripts/plan_creator.py` | Generate Plan.md from tasks |
| `scripts/linkedin_poster.py` | LinkedIn automation |
| `scripts/scheduler_manager.py` | Cron job management |

### MCP Servers
| Server | Purpose |
|--------|---------|
| `mcp_servers/email_server.py` | Email operations via MCP |

### Skills (.claude/skills/)
| Skill | Purpose |
|-------|---------|
| `approval_workflow.md` | Human-in-the-loop approval |
| `gmail_watcher.md` | Email monitoring |
| `linkedin_poster.md` | Social media posting |
| `plan_creator.md` | Task planning |
| `email_sender.md` | Email via MCP |
| `scheduler.md` | Cron scheduling |

---

## Testing

### Test Bronze Tier
```bash
# Terminal 1
python3 filesystem_watcher.py

# Terminal 2
echo "Test task" > AI_Employee_Vault/Inbox/test.txt

# Terminal 2
python3 agent_executor.py
```

### Test Silver Tier
```bash
# Test Gmail watcher (simulation)
python3 watchers/gmail_watcher.py --simulate

# Test Plan Creator
python3 scripts/plan_creator.py

# Test MCP Server
python3 mcp_servers/email_server.py --test

# Test LinkedIn (simulation)
python3 scripts/linkedin_poster.py
```

---

## Workflow Examples

### Email Processing Flow
```
1. Email arrives → Gmail Watcher detects
2. Task created → /Needs_Action/email/
3. Plan Creator → Generates Plan.md
4. If reply needed → Approval request created
5. Human approves → MCP sends email
6. Task → /Done/
```

### LinkedIn Posting Flow
```
1. Post request → /Pending_Approval/
2. Human reviews → Moves to /Approved/
3. Approval Watcher → Triggers LinkedIn poster
4. Post published → Logged to /Done/
```

---

## Scheduling (Cron)

View/install schedules:
```bash
python3 scripts/scheduler_manager.py list
python3 scripts/scheduler_manager.py install
```

---

## Security

- All data stored locally (no cloud dependencies)
- Credentials stored in `secrets/` (not in vault)
- Human approval required for external actions
- All actions logged for audit

---

## Future Enhancements (Gold Tier)

- [ ] Odoo integration
- [ ] Facebook/Instagram integration
- [ ] Weekly CEO Briefing
- [ ] Ralph Wiggum loop
- [ ] Full error recovery

---

*Built with Claude Code + Obsidian*
*Personal AI Employee Hackathon 0*
