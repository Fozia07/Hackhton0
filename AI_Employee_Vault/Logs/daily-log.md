# Daily Log Documentation

---

## Purpose

This document defines the daily logging workflow for the Bronze Tier task management system. Daily logs provide a permanent record of all operational activities, decisions, and task movements. They serve as an audit trail, support accountability, and enable historical analysis of system performance.

---

## Daily Log Entry Template

Each daily log entry must follow this standardized format:

```
# Daily Log: [YYYY-MM-DD]

---

## Log Information

**Date:** [YYYY-MM-DD]
**Log Author:** [Name]
**Time Started:** [HH:MM]
**Time Ended:** [HH:MM]

---

## Summary

[Brief narrative summary of the day's operations, key accomplishments, and notable events.]

---

## Tasks Created

| Task ID | Task Title | Priority | Assigned To |
|---------|------------|----------|-------------|
| [ID] | [Title] | [Priority] | [Name] |

**Total Created:** [0]

---

## Tasks Completed

| Task ID | Task Title | Completed By | Completion Time |
|---------|------------|--------------|-----------------|
| [ID] | [Title] | [Name] | [HH:MM] |

**Total Completed:** [0]

---

## Approvals Processed

| Task ID | Task Title | Decision | Approver | Reason/Notes |
|---------|------------|----------|----------|--------------|
| [ID] | [Title] | Approved/Rejected | [Name] | [Notes] |

**Total Approved:** [0]
**Total Rejected:** [0]

---

## Task Movements

| Task ID | From Folder | To Folder | Moved By | Time |
|---------|-------------|-----------|----------|------|
| [ID] | [Source] | [Destination] | [Name] | [HH:MM] |

---

## Issues Encountered

| Issue | Severity | Task Affected | Resolution | Status |
|-------|----------|---------------|------------|--------|
| [Description] | Low/Medium/High/Critical | [Task ID or N/A] | [Action taken] | Resolved/Pending |

---

## Decisions Made

| Decision | Context | Made By | Impact |
|----------|---------|---------|--------|
| [Decision] | [Why it was needed] | [Name] | [Effect on workflow] |

---

## Blocked Tasks Update

| Task ID | Blocking Reason | Action Taken | Current Status |
|---------|-----------------|--------------|----------------|
| [ID] | [Reason] | [Action] | Blocked/Unblocked |

---

## End of Day Status

| Folder | Count |
|--------|-------|
| Needs_Action | [0] |
| Plans | [0] |
| Pending_Approval | [0] |
| Approved | [0] |
| Rejected | [0] |
| Done | [0] |

---

## Notes and Observations

[Any additional notes, observations, or recommendations for future reference.]

---

## Sign-Off

**Logged By:** [Name]
**Log Completed:** [YYYY-MM-DD HH:MM]

---
```

---

## Required Fields

Every daily log must include the following mandatory fields:

### Header Information
| Field | Description | Required |
|-------|-------------|----------|
| Date | The date of the log (YYYY-MM-DD) | Yes |
| Log Author | Name of person creating the log | Yes |
| Time Started | Start time of operations | Yes |
| Time Ended | End time of operations | Yes |

### Activity Records
| Field | Description | Required |
|-------|-------------|----------|
| Summary | Narrative overview of the day | Yes |
| Tasks Created | List of all new tasks | Yes (even if zero) |
| Tasks Completed | List of all completed tasks | Yes (even if zero) |
| Approvals Processed | All approval decisions made | Yes (even if zero) |
| Task Movements | Record of all folder transfers | Yes (even if none) |

### Status Records
| Field | Description | Required |
|-------|-------------|----------|
| End of Day Status | Count of tasks in each folder | Yes |
| Issues Encountered | Problems that arose | Yes (even if none) |
| Sign-Off | Author confirmation | Yes |

### Optional Fields
| Field | Description | When to Include |
|-------|-------------|-----------------|
| Decisions Made | Significant decisions | When applicable |
| Blocked Tasks Update | Blocking status changes | When applicable |
| Notes and Observations | Additional context | As needed |

---

## Naming Convention

### File Naming Format

```
YYYY-MM-DD_daily-log.md
```

### Examples

| Date | File Name |
|------|-----------|
| February 17, 2026 | `2026-02-17_daily-log.md` |
| March 1, 2026 | `2026-03-01_daily-log.md` |
| December 31, 2026 | `2026-12-31_daily-log.md` |

### Naming Rules

1. Always use four-digit year (YYYY)
2. Always use two-digit month (MM) with leading zero
3. Always use two-digit day (DD) with leading zero
4. Use underscores to separate date from description
5. Use hyphens within the date components
6. Always use lowercase for text portions
7. Always use `.md` extension

---

## Logging Rules

### Creation Rules

1. **One Log Per Day**: Create exactly one daily log file per operational day
2. **Create at Start of Day**: Initialize the log at the beginning of operations
3. **Update Throughout Day**: Add entries as activities occur
4. **Finalize at End of Day**: Complete all sections and sign off before day ends

### Content Rules

1. **Be Factual**: Record only facts, not opinions or speculation
2. **Be Complete**: Document all task movements, decisions, and issues
3. **Be Timely**: Log activities as they occur, not from memory
4. **Be Consistent**: Use the standard template format for all entries
5. **Be Accurate**: Verify task IDs and names before logging

### Storage Rules

1. **Location**: All daily logs are stored in `/Bronze-tier/Logs/`
2. **No Modifications**: Once finalized, logs should not be altered
3. **Corrections**: If corrections are needed, add an amendment section dated with the correction date
4. **Retention**: Logs are retained indefinitely

### Access Rules

1. Logs are read-only after sign-off
2. Any team member may view logs
3. Only designated personnel may create official logs
4. Audit access must be available upon request

---

## Example Log Entry Format

Below is the structural format for a daily log entry. This shows the organization and layout without sample data:

```
# Daily Log: [DATE]

---

## Log Information

**Date:** [DATE]
**Log Author:** [AUTHOR]
**Time Started:** [TIME]
**Time Ended:** [TIME]

---

## Summary

[NARRATIVE SUMMARY PARAGRAPH]

---

## Tasks Created

| Task ID | Task Title | Priority | Assigned To |
|---------|------------|----------|-------------|
| | | | |

**Total Created:** [COUNT]

---

## Tasks Completed

| Task ID | Task Title | Completed By | Completion Time |
|---------|------------|--------------|-----------------|
| | | | |

**Total Completed:** [COUNT]

---

## Approvals Processed

| Task ID | Task Title | Decision | Approver | Reason/Notes |
|---------|------------|----------|----------|--------------|
| | | | | |

**Total Approved:** [COUNT]
**Total Rejected:** [COUNT]

---

## Task Movements

| Task ID | From Folder | To Folder | Moved By | Time |
|---------|-------------|-----------|----------|------|
| | | | | |

---

## Issues Encountered

| Issue | Severity | Task Affected | Resolution | Status |
|-------|----------|---------------|------------|--------|
| | | | | |

---

## Decisions Made

| Decision | Context | Made By | Impact |
|----------|---------|---------|--------|
| | | | |

---

## Blocked Tasks Update

| Task ID | Blocking Reason | Action Taken | Current Status |
|---------|-----------------|--------------|----------------|
| | | | |

---

## End of Day Status

| Folder | Count |
|--------|-------|
| Needs_Action | [COUNT] |
| Plans | [COUNT] |
| Pending_Approval | [COUNT] |
| Approved | [COUNT] |
| Rejected | [COUNT] |
| Done | [COUNT] |

---

## Notes and Observations

[ADDITIONAL NOTES]

---

## Sign-Off

**Logged By:** [NAME]
**Log Completed:** [DATE TIME]

---
```

---

## Quick Reference

### Log Checklist

Before finalizing a daily log, verify:

- [ ] Date is correct
- [ ] All task movements are recorded
- [ ] All approvals/rejections are documented
- [ ] End of day counts are accurate
- [ ] Issues section is complete (even if "None")
- [ ] Log author is identified
- [ ] Sign-off is complete with timestamp

### Common Errors to Avoid

| Error | Prevention |
|-------|------------|
| Missing task movements | Review each folder for changes |
| Incorrect task IDs | Copy IDs directly from task files |
| Missing timestamps | Log activities in real-time |
| Incomplete summaries | Write summary before sign-off |
| Unsigned logs | Never finalize without sign-off |

---

*Document Version: 1.0*
*Last Updated: 2026-02-17*
