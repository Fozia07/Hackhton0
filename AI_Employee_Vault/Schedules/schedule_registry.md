---
type: schedule_registry
updated: 2026-02-21T02:44:19.862733
---

# Schedule Registry

## Active Cron Schedules

| ID | Description | Schedule | Script | Status |
|----|-------------|----------|--------|--------|

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
*Last Updated: 2026-02-21 02:44:19*
