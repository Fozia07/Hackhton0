
# AI Employee Skills Index

## Silver + Gold Tier Skills Registry

**Last Updated:** 2026-02-25
**Total Skills:** 10
**Location:** `/.claude/skills/`

---

## Available Skills

| Skill | File | Purpose | Tier |
|-------|------|---------|------|
| CEO Briefing | `ceo-briefing.md` | Weekly business audit & executive report | **Gold** |
| Audit Logging | `audit-logging.md` | Enterprise-grade JSON audit logging | **Gold** |
| Error Recovery | `error-recovery.md` | Retry handling & circuit breaker patterns | **Gold** |
| AI Employee Runner | `ai_employee_runner.md` | Production-ready automated scheduler | Silver |
| Approval Workflow | `approval_workflow.md` | Human-in-the-loop approval for sensitive actions | Silver |
| Gmail Watcher | `gmail_watcher.md` | Monitor Gmail for new emails | Silver |
| LinkedIn Poster | `linkedin_poster.md` | Automated LinkedIn posting via Playwright | Silver |
| Plan Creator | `plan_creator.md` | Generate Plan.md files from tasks | Silver |
| Email Sender | `email_sender.md` | Send emails via MCP server | Silver |
| Scheduler | `scheduler.md` | Cron-based task scheduling | Silver |

---

## Skills by Category

### Perception (Watchers)
- **Gmail Watcher** - Monitors email inbox
- **Filesystem Watcher** - Monitors local files (Bronze)

### Reasoning (Planning)
- **Plan Creator** - Generates execution plans

### Action (External)
- **Email Sender** - Sends emails via MCP
- **LinkedIn Poster** - Posts to LinkedIn

### Workflow (Management)
- **Approval Workflow** - Human-in-the-loop decisions
- **Scheduler** - Automated task scheduling

### Orchestration
- **AI Employee Runner** - Master scheduler, runs every 5 minutes

### Business Intelligence (Gold)
- **CEO Briefing** - Weekly business audit & Monday morning report

### System Operations (Gold)
- **Audit Logging** - Enterprise-grade JSON audit logging for all operations
- **Error Recovery** - Retry handling, circuit breaker, failure classification

---

## Skill Invocation

### Via Command
```
/skill {skill_name} {parameters}
```

### Via Task File
When a task file includes `skill_required: {skill_name}` in frontmatter.

### Via Orchestrator
Orchestrator automatically invokes skills based on task type.

---

## Skill Dependencies

```
┌─────────────────────────────────────────────────┐
│                  SKILL FLOW                      │
├─────────────────────────────────────────────────┤
│                                                  │
│  Gmail Watcher ──┐                              │
│                  ├──► Plan Creator              │
│  Filesystem ─────┘         │                    │
│                            ▼                    │
│                    Approval Workflow            │
│                            │                    │
│              ┌─────────────┼─────────────┐      │
│              ▼             ▼             ▼      │
│        Email Sender  LinkedIn Poster  [Done]   │
│                                                  │
│              All scheduled via: Scheduler        │
└─────────────────────────────────────────────────┘
```

---

## Skill Status

| Skill | Definition | Implementation | Testing |
|-------|------------|----------------|---------|
| CEO Briefing (Gold) | ✅ | ✅ Complete | ✅ Passed |
| Audit Logging (Gold) | ✅ | ✅ Complete | ✅ Passed |
| Error Recovery (Gold) | ✅ | ✅ Complete | ✅ Passed |
| AI Employee Runner | ✅ | ✅ Complete | ✅ Passed |
| Approval Workflow | ✅ | ✅ Complete | ✅ Passed |
| Gmail Watcher | ✅ | ✅ Complete | ✅ Passed |
| LinkedIn Poster | ✅ | ✅ Complete | ✅ Passed |
| Plan Creator | ✅ | ✅ Complete | ✅ Passed |
| Email Sender | ✅ | ✅ Complete | ✅ Passed |
| Scheduler | ✅ | ✅ Complete | ✅ Passed |

---

## Quick Reference

### Skill File Structure
```
/.claude/skills/
├── SKILLS_INDEX.md          # This file
├── ceo-briefing.md          # CEO Briefing (Gold)
├── audit-logging.md         # Audit Logging (Gold)
├── error-recovery.md        # Error Recovery (Gold)
├── ai_employee_runner.md    # Master orchestrator
├── approval_workflow.md     # HITL approval
├── gmail_watcher.md         # Email monitoring
├── linkedin_poster.md       # Social posting
├── plan_creator.md          # Task planning
├── email_sender.md          # Email via MCP
└── scheduler.md             # Cron scheduling
```

### Common Commands
```
/skill approval_workflow --action send_email
/skill gmail_watcher --check
/skill linkedin_poster --content "..."
/skill plan_creator --task /Needs_Action/task.md
/skill email_sender --to user@example.com
/skill scheduler --list
```

---

*Skills Index - Silver + Gold Tier*
