"""
Scheduler Manager - Cron Job Management
Silver Tier Component

Manages scheduled tasks for the AI Employee system.
Based on: Skills/scheduler.md
"""

import os
import subprocess
import json
from datetime import datetime
from pathlib import Path

# Configuration
BASE_DIR = Path(__file__).parent.parent
VAULT_DIR = BASE_DIR / "AI_Employee_Vault"
SCHEDULES_DIR = VAULT_DIR / "Schedules"
LOGS_DIR = VAULT_DIR / "Logs"
CRONTAB_TEMPLATE = BASE_DIR / "scripts" / "crontab_template"


def log(message, level="INFO"):
    """Print a timestamped log message."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}")


def get_current_crontab():
    """Get current user's crontab."""
    try:
        result = subprocess.run(
            ["crontab", "-l"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return result.stdout
        return ""
    except Exception as e:
        log(f"Error reading crontab: {e}", "ERROR")
        return ""


def install_crontab():
    """Install the crontab from template."""
    if not CRONTAB_TEMPLATE.exists():
        log(f"Crontab template not found: {CRONTAB_TEMPLATE}", "ERROR")
        return False

    try:
        result = subprocess.run(
            ["crontab", str(CRONTAB_TEMPLATE)],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            log("Crontab installed successfully")
            return True
        else:
            log(f"Failed to install crontab: {result.stderr}", "ERROR")
            return False
    except Exception as e:
        log(f"Error installing crontab: {e}", "ERROR")
        return False


def list_schedules():
    """List all active schedules."""
    crontab = get_current_crontab()

    if not crontab:
        print("No crontab entries found.")
        return

    print("=" * 60)
    print("ACTIVE SCHEDULES")
    print("=" * 60)

    lines = crontab.strip().split("\n")
    schedule_count = 0

    for line in lines:
        line = line.strip()
        if line and not line.startswith("#") and not line.startswith("SHELL") and not line.startswith("PATH") and not line.startswith("MAILTO") and not "=" in line.split()[0]:
            schedule_count += 1
            parts = line.split()
            if len(parts) >= 6:
                timing = " ".join(parts[:5])
                command = " ".join(parts[5:])
                # Extract script name
                script = "unknown"
                if ".py" in command:
                    for part in command.split():
                        if ".py" in part:
                            script = Path(part).name
                            break
                print(f"{schedule_count}. [{timing}] {script}")

    print("=" * 60)
    print(f"Total active schedules: {schedule_count}")


def parse_cron_expression(expr):
    """Parse a cron expression and return human-readable format."""
    parts = expr.split()
    if len(parts) != 5:
        return "Invalid expression"

    minute, hour, day, month, weekday = parts

    # Simple parsing
    if expr == "* * * * *":
        return "Every minute"
    if expr.startswith("*/"):
        interval = parts[0].replace("*/", "")
        return f"Every {interval} minutes"
    if minute == "0" and hour != "*":
        if weekday == "*":
            return f"Daily at {hour}:00"
        elif weekday == "1-5":
            return f"Weekdays at {hour}:00"
        else:
            return f"At {hour}:00"

    return expr


def create_schedule_registry():
    """Create a schedule registry file in the vault."""
    SCHEDULES_DIR.mkdir(parents=True, exist_ok=True)
    registry_file = SCHEDULES_DIR / "schedule_registry.md"

    crontab = get_current_crontab()

    content = f"""---
type: schedule_registry
updated: {datetime.now().isoformat()}
---

# Schedule Registry

## Active Cron Schedules

| ID | Description | Schedule | Script | Status |
|----|-------------|----------|--------|--------|
"""

    if crontab:
        lines = crontab.strip().split("\n")
        schedule_id = 1

        for line in lines:
            line = line.strip()
            if line and not line.startswith("#") and not line.startswith("SHELL") and not line.startswith("PATH") and not line.startswith("MAILTO") and not "=" in line.split()[0]:
                parts = line.split()
                if len(parts) >= 6:
                    timing = " ".join(parts[:5])
                    command = " ".join(parts[5:])

                    # Extract script name
                    script = "unknown"
                    description = "Scheduled task"

                    for part in command.split():
                        if ".py" in part:
                            script = Path(part).name
                            # Generate description from script name
                            description = script.replace("_", " ").replace(".py", "").title()
                            break

                    human_timing = parse_cron_expression(timing)

                    content += f"| SCH{schedule_id:03d} | {description} | {human_timing} | `{script}` | Active |\n"
                    schedule_id += 1

    content += f"""
## Schedule Legend

| Symbol | Meaning |
|--------|---------|
| * | Every |
| */N | Every N units |
| 0-23 | Hour (24h format) |
| 1-5 | Monday to Friday |

## Management Commands

```bash
# View current schedules
crontab -l

# Edit schedules
crontab -e

# Install from template
crontab scripts/crontab_template
```

---
*Last Updated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}*
"""

    with open(registry_file, "w") as f:
        f.write(content)

    log(f"Schedule registry created: {registry_file}")


def show_help():
    """Display help information."""
    print("""
Scheduler Manager - AI Employee Silver Tier
============================================

Usage: python scheduler_manager.py [command]

Commands:
  list      - Show all active schedules
  install   - Install crontab from template
  registry  - Create schedule registry in vault
  help      - Show this help message

Examples:
  python scheduler_manager.py list
  python scheduler_manager.py install
  python scheduler_manager.py registry
""")


def main():
    import sys

    if len(sys.argv) < 2:
        show_help()
        return

    command = sys.argv[1].lower()

    if command == "list":
        list_schedules()
    elif command == "install":
        install_crontab()
    elif command == "registry":
        create_schedule_registry()
    elif command == "help":
        show_help()
    else:
        print(f"Unknown command: {command}")
        show_help()


if __name__ == "__main__":
    main()
