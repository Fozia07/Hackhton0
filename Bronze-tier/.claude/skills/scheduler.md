# Skill: Scheduler

## Description
Manages scheduled tasks using cron jobs (Linux).
Triggers watchers, briefings, and automated workflows at defined times.

## Trigger
- Cron job execution
- Manual schedule creation
- Command: `/schedule`, `/list-schedules`

## Inputs
| Input | Type | Required | Description |
|-------|------|----------|-------------|
| task_name | String | Yes | Name of task to schedule |
| cron_expression | String | Yes | Cron timing expression |
| script_path | String | Yes | Script to execute |
| enabled | Boolean | No | Whether schedule is active (default: true) |

## Process

### Step 1: Schedule Creation
1. Validate cron expression
2. Verify script exists
3. Create schedule entry
4. Register with system cron

### Step 2: Cron Registration
1. Add entry to user crontab
2. Set environment variables
3. Configure logging

### Step 3: Execution Monitoring
1. Log each execution
2. Track success/failure
3. Alert on repeated failures

### Step 4: Schedule Management
1. List active schedules
2. Enable/disable schedules
3. Remove schedules

## Output
| Output | Type | Description |
|--------|------|-------------|
| schedule_id | String | Unique schedule identifier |
| cron_entry | String | Registered cron expression |
| status | String | active, disabled, error |
| next_run | DateTime | Next scheduled execution |

## Cron Expression Guide

```
┌───────────── minute (0-59)
│ ┌───────────── hour (0-23)
│ │ ┌───────────── day of month (1-31)
│ │ │ ┌───────────── month (1-12)
│ │ │ │ ┌───────────── day of week (0-6, Sunday=0)
│ │ │ │ │
* * * * *
```

### Common Patterns

| Schedule | Cron Expression | Description |
|----------|-----------------|-------------|
| Every 5 minutes | `*/5 * * * *` | Frequent checks |
| Hourly | `0 * * * *` | Every hour |
| Daily 8 AM | `0 8 * * *` | Morning trigger |
| Daily 6 PM | `0 18 * * *` | Evening trigger |
| Weekly Monday | `0 9 * * 1` | Weekly at 9 AM |
| Monthly 1st | `0 0 1 * *` | Monthly midnight |

## Recommended Schedules for AI Employee

### Gmail Watcher
```
*/5 * * * * python3 /path/to/watchers/gmail_watcher.py >> /path/to/logs/gmail.log 2>&1
```

### Daily Briefing
```
0 8 * * * python3 /path/to/scripts/daily_briefing.py >> /path/to/logs/briefing.log 2>&1
```

### LinkedIn Auto-Post (if scheduled)
```
0 10 * * 1-5 python3 /path/to/scripts/linkedin_scheduler.py >> /path/to/logs/linkedin.log 2>&1
```

### Approval Watcher
```
*/3 * * * * python3 /path/to/watchers/approval_watcher.py >> /path/to/logs/approval.log 2>&1
```

### Filesystem Watcher (runs continuously, started at boot)
```
@reboot python3 /path/to/watchers/filesystem_watcher.py >> /path/to/logs/filesystem.log 2>&1
```

## Schedule Registry Template

```markdown
---
type: schedule_registry
updated: {ISO_timestamp}
---

# Active Schedules

| ID | Task | Cron | Script | Status | Last Run |
|----|------|------|--------|--------|----------|
| SCH001 | Gmail Check | */5 * * * * | gmail_watcher.py | Active | {timestamp} |
| SCH002 | Daily Brief | 0 8 * * * | daily_briefing.py | Active | {timestamp} |
| SCH003 | Approval Watch | */3 * * * * | approval_watcher.py | Active | {timestamp} |

## Execution Log (Last 10)

| Timestamp | Schedule | Result |
|-----------|----------|--------|
| {time} | {name} | Success/Failed |

---
*Scheduler Skill Registry*
```

## Example Usage

```
Skill: scheduler
Input:
  task_name: "Gmail Watcher"
  cron_expression: "*/5 * * * *"
  script_path: "/path/to/watchers/gmail_watcher.py"
  enabled: true

Output:
  schedule_id: "SCH_gmail_watcher_001"
  cron_entry: "*/5 * * * * python3 /path/to/watchers/gmail_watcher.py"
  status: "active"
  next_run: "2026-02-20T14:35:00Z"
```

## Crontab Management Commands

### View current crontab
```bash
crontab -l
```

### Edit crontab
```bash
crontab -e
```

### Install from file
```bash
crontab /path/to/crontab_file
```

## Safety Rules
- Never schedule destructive operations
- Always include logging for audit
- Set reasonable intervals (no less than 1 min)
- Monitor for runaway processes
- Use flock to prevent overlapping runs

## Error Recovery
- Log all failures
- Retry with exponential backoff
- Alert after 3 consecutive failures
- Auto-disable after 10 failures

---
*Skill Version: 1.0 | Silver Tier*
