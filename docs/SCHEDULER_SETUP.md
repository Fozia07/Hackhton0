# AI Employee Scheduler Setup Guide

Complete guide to set up automatic execution of the AI Employee system every 5 minutes.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Test](#quick-test)
3. [Linux / Mac Setup (Cron)](#linux--mac-setup-cron)
4. [Windows Setup (Task Scheduler)](#windows-setup-task-scheduler)
5. [Verification](#verification)
6. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Python Requirements

```bash
# Ensure Python 3.10+ is installed
python3 --version

# No additional packages required - uses standard library only
```

### Verify Script Location

```
Bronze-tier/
├── scripts/
│   └── run_ai_employee.py    # Main scheduler script
├── AI_Employee_Vault/
│   ├── Inbox/
│   ├── Needs_Action/
│   ├── Done/
│   └── Logs/
└── .claude/
    └── skills/
```

---

## Quick Test

Before setting up scheduled execution, test the script manually:

```bash
# Navigate to project directory
cd /path/to/Bronze-tier

# Test single cycle (dry run - no changes)
python3 scripts/run_ai_employee.py --once --dry-run

# Test single cycle (actual execution)
python3 scripts/run_ai_employee.py --once

# Test with verbose output
python3 scripts/run_ai_employee.py --once --verbose
```

Expected output:
```
============================================================
   AI Employee Runner - Silver Tier
   Production-Ready Automated Scheduler
============================================================
   Mode: Single Cycle
   Dry Run: False
   Verbose: False
============================================================

[2026-02-24 10:00:00] [INFO] Running single cycle
[2026-02-24 10:00:00] [INFO] === Starting cycle 20260224_100000 ===
[2026-02-24 10:00:00] [INFO] Found 0 items in Inbox
[2026-02-24 10:00:00] [INFO] Found 0 items in Needs_Action
[2026-02-24 10:00:00] [INFO] Found 0 items in Approved
[2026-02-24 10:00:00] [INFO] === Cycle 20260224_100000 complete ===

Cycle Result:
{
  "cycle_id": "20260224_100000",
  "tasks_processed": 0,
  "tasks_completed": 0,
  ...
}
```

---

## Linux / Mac Setup (Cron)

### Option 1: User Crontab (Recommended)

```bash
# Open user crontab editor
crontab -e
```

Add the following line (adjust paths):

```cron
# AI Employee Runner - Run every 5 minutes
*/5 * * * * cd /path/to/Bronze-tier && /usr/bin/python3 scripts/run_ai_employee.py --once >> AI_Employee_Vault/Logs/cron.log 2>&1
```

### Option 2: With Environment Variables

```cron
# AI Employee Runner with custom config
*/5 * * * * AI_EMPLOYEE_VAULT=/path/to/AI_Employee_Vault /usr/bin/python3 /path/to/Bronze-tier/scripts/run_ai_employee.py --once >> /path/to/Bronze-tier/AI_Employee_Vault/Logs/cron.log 2>&1
```

### Option 3: Using a Wrapper Script

Create `/path/to/Bronze-tier/scripts/run_scheduled.sh`:

```bash
#!/bin/bash
# AI Employee Scheduled Runner

# Set environment
export PATH="/usr/local/bin:/usr/bin:$PATH"
export AI_EMPLOYEE_VAULT="/path/to/Bronze-tier/AI_Employee_Vault"

# Navigate to project
cd /path/to/Bronze-tier

# Run with logging
/usr/bin/python3 scripts/run_ai_employee.py --once \
    >> AI_Employee_Vault/Logs/cron.log 2>&1

# Optional: Notify on failure
if [ $? -ne 0 ]; then
    echo "AI Employee Runner failed at $(date)" >> AI_Employee_Vault/Logs/errors.log
fi
```

Make executable and add to cron:

```bash
chmod +x /path/to/Bronze-tier/scripts/run_scheduled.sh

# Add to crontab
crontab -e
```

```cron
*/5 * * * * /path/to/Bronze-tier/scripts/run_scheduled.sh
```

### Verify Cron Setup

```bash
# List current crontab
crontab -l

# Check cron service status (Linux)
systemctl status cron

# Check cron service status (Mac)
sudo launchctl list | grep cron

# Monitor cron log
tail -f /var/log/syslog | grep CRON   # Linux
tail -f /var/log/system.log | grep cron  # Mac
```

### Using Systemd Timer (Alternative for Linux)

Create service file `/etc/systemd/system/ai-employee.service`:

```ini
[Unit]
Description=AI Employee Runner
After=network.target

[Service]
Type=oneshot
User=your_username
WorkingDirectory=/path/to/Bronze-tier
ExecStart=/usr/bin/python3 scripts/run_ai_employee.py --once
StandardOutput=append:/path/to/Bronze-tier/AI_Employee_Vault/Logs/systemd.log
StandardError=append:/path/to/Bronze-tier/AI_Employee_Vault/Logs/systemd.log

[Install]
WantedBy=multi-user.target
```

Create timer file `/etc/systemd/system/ai-employee.timer`:

```ini
[Unit]
Description=Run AI Employee every 5 minutes

[Timer]
OnBootSec=1min
OnUnitActiveSec=5min
AccuracySec=1sec

[Install]
WantedBy=timers.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable ai-employee.timer
sudo systemctl start ai-employee.timer

# Check status
systemctl status ai-employee.timer
systemctl list-timers | grep ai-employee
```

---

## Windows Setup (Task Scheduler)

### Option 1: Using Task Scheduler GUI

1. **Open Task Scheduler**
   - Press `Win + R`, type `taskschd.msc`, press Enter

2. **Create New Task**
   - Click "Create Task..." in the right panel

3. **General Tab**
   - Name: `AI Employee Runner`
   - Description: `Runs AI Employee system every 5 minutes`
   - Select: "Run whether user is logged on or not"
   - Check: "Run with highest privileges"

4. **Triggers Tab**
   - Click "New..."
   - Begin the task: "On a schedule"
   - Settings: "Daily"
   - Start: Select today's date, time: `00:00:00`
   - Recur every: `1` days
   - Check: "Repeat task every: `5 minutes`"
   - For a duration of: `Indefinitely`
   - Check: "Enabled"
   - Click "OK"

5. **Actions Tab**
   - Click "New..."
   - Action: "Start a program"
   - Program/script: `python` or `C:\Python312\python.exe`
   - Add arguments: `scripts\run_ai_employee.py --once`
   - Start in: `C:\Users\Fozia\Hackhton0\Bronze-tier`
   - Click "OK"

6. **Conditions Tab**
   - Uncheck: "Start the task only if the computer is on AC power"

7. **Settings Tab**
   - Check: "Allow task to be run on demand"
   - Check: "Run task as soon as possible after a scheduled start is missed"
   - Check: "If the task fails, restart every: `1 minute`"
   - Attempt to restart up to: `3` times
   - Check: "Stop the task if it runs longer than: `4 minutes`"
   - Click "OK"

8. **Enter Password** when prompted

### Option 2: Using PowerShell Script

Save as `setup_task_scheduler.ps1`:

```powershell
# AI Employee Task Scheduler Setup Script
# Run as Administrator

$TaskName = "AI Employee Runner"
$TaskPath = "\AI Employee\"
$PythonPath = "python"  # Or full path: "C:\Python312\python.exe"
$ScriptPath = "C:\Users\Fozia\Hackhton0\Bronze-tier\scripts\run_ai_employee.py"
$WorkingDir = "C:\Users\Fozia\Hackhton0\Bronze-tier"
$LogPath = "C:\Users\Fozia\Hackhton0\Bronze-tier\AI_Employee_Vault\Logs\task_scheduler.log"

# Remove existing task if exists
Unregister-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath -Confirm:$false -ErrorAction SilentlyContinue

# Create action
$Action = New-ScheduledTaskAction `
    -Execute $PythonPath `
    -Argument "scripts\run_ai_employee.py --once" `
    -WorkingDirectory $WorkingDir

# Create trigger (every 5 minutes)
$Trigger = New-ScheduledTaskTrigger `
    -Once `
    -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Minutes 5) `
    -RepetitionDuration (New-TimeSpan -Days 9999)

# Create settings
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 4)

# Create principal (run with highest privileges)
$Principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType S4U `
    -RunLevel Highest

# Register task
Register-ScheduledTask `
    -TaskName $TaskName `
    -TaskPath $TaskPath `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Principal $Principal `
    -Description "Runs AI Employee system every 5 minutes"

Write-Host "Task '$TaskName' created successfully!"
Write-Host "Use 'taskschd.msc' to verify."
```

Run in PowerShell as Administrator:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\setup_task_scheduler.ps1
```

### Option 3: Using schtasks Command

```cmd
:: Create scheduled task via command line
schtasks /create ^
    /tn "AI Employee\AI Employee Runner" ^
    /tr "python C:\Users\Fozia\Hackhton0\Bronze-tier\scripts\run_ai_employee.py --once" ^
    /sc minute ^
    /mo 5 ^
    /st 00:00 ^
    /ru "%USERNAME%" ^
    /rl HIGHEST ^
    /f

:: Verify
schtasks /query /tn "AI Employee\AI Employee Runner"

:: Run immediately (test)
schtasks /run /tn "AI Employee\AI Employee Runner"

:: Delete if needed
schtasks /delete /tn "AI Employee\AI Employee Runner" /f
```

### Windows Batch Wrapper Script

Create `run_scheduled.bat` in Bronze-tier folder:

```batch
@echo off
:: AI Employee Scheduled Runner for Windows

:: Set working directory
cd /d "C:\Users\Fozia\Hackhton0\Bronze-tier"

:: Set timestamp
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set datetime=%%I
set timestamp=%datetime:~0,4%-%datetime:~4,2%-%datetime:~6,2% %datetime:~8,2%:%datetime:~10,2%:%datetime:~12,2%

:: Log start
echo [%timestamp%] Starting AI Employee Runner >> AI_Employee_Vault\Logs\batch.log

:: Run Python script
python scripts\run_ai_employee.py --once >> AI_Employee_Vault\Logs\batch.log 2>&1

:: Log completion
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set datetime=%%I
set timestamp=%datetime:~0,4%-%datetime:~4,2%-%datetime:~6,2% %datetime:~8,2%:%datetime:~10,2%:%datetime:~12,2%
echo [%timestamp%] Completed >> AI_Employee_Vault\Logs\batch.log
```

---

## Verification

### Check If Running

**Linux/Mac:**
```bash
# Check cron logs
tail -f /path/to/Bronze-tier/AI_Employee_Vault/Logs/cron.log

# Check runner logs
tail -f /path/to/Bronze-tier/AI_Employee_Vault/Logs/runner.log

# Check JSON logs
cat /path/to/Bronze-tier/AI_Employee_Vault/Logs/$(date +%Y-%m-%d)_runner.json | python3 -m json.tool
```

**Windows:**
```powershell
# Check task status
Get-ScheduledTask -TaskName "AI Employee Runner" | Get-ScheduledTaskInfo

# View recent runs
Get-WinEvent -LogName "Microsoft-Windows-TaskScheduler/Operational" |
    Where-Object { $_.Message -like "*AI Employee*" } |
    Select-Object -First 10

# Check logs
Get-Content "C:\Users\Fozia\Hackhton0\Bronze-tier\AI_Employee_Vault\Logs\runner.log" -Tail 50
```

### Test the Workflow

1. Create a test file:
```bash
echo "Test task for AI Employee" > AI_Employee_Vault/Inbox/test_task.txt
```

2. Wait for next scheduled run (or run manually)

3. Verify file was processed:
```bash
ls AI_Employee_Vault/Needs_Action/general/
# Should see test_task.txt and TASK_GENERAL_*.md
```

---

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| "Another instance is already running" | Delete `.ai_employee.lock` file |
| "Permission denied" | Check file/folder permissions |
| "Python not found" | Use full path to Python executable |
| Script doesn't run | Check cron/Task Scheduler logs |
| No output in logs | Check working directory is correct |

### Debug Mode

```bash
# Run with verbose output
python3 scripts/run_ai_employee.py --once --verbose

# Check Python path
which python3  # Linux/Mac
where python   # Windows
```

### Lock File Issues

```bash
# Remove stale lock file
rm /path/to/Bronze-tier/.ai_employee.lock

# Windows
del "C:\Users\Fozia\Hackhton0\Bronze-tier\.ai_employee.lock"
```

### Cron Not Running

```bash
# Check cron service
sudo systemctl status cron
sudo systemctl restart cron

# Check crontab syntax
crontab -l

# Test command manually
cd /path/to/Bronze-tier && python3 scripts/run_ai_employee.py --once
```

### Task Scheduler Not Running

1. Open Event Viewer (`eventvwr.msc`)
2. Navigate to: Windows Logs > System
3. Look for Task Scheduler errors

Or check:
```powershell
Get-ScheduledTask -TaskName "AI Employee Runner" | Format-List *
```

---

## Log Locations

| Log Type | Location |
|----------|----------|
| Human-readable | `AI_Employee_Vault/Logs/runner.log` |
| JSON structured | `AI_Employee_Vault/Logs/YYYY-MM-DD_runner.json` |
| Cron output | `AI_Employee_Vault/Logs/cron.log` |
| Dashboard | `AI_Employee_Vault/Dashboard.md` |

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AI_EMPLOYEE_VAULT` | Auto-detected | Path to vault |
| `AI_EMPLOYEE_CYCLE_INTERVAL` | 300 | Seconds between cycles |
| `AI_EMPLOYEE_MAX_TASKS` | 20 | Max tasks per cycle |
| `AI_EMPLOYEE_LOG_LEVEL` | INFO | Logging level |

---

*AI Employee Scheduler Setup Guide - Silver Tier*
