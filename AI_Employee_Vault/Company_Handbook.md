# Company Handbook

---

## Purpose

This handbook defines the operational workflow for the Bronze Tier task management system. It establishes clear rules for how tasks are created, processed, approved, and completed. All team members and automated systems must follow these guidelines to ensure consistency, accountability, and traceability.

---

## Task Lifecycle Flow

Every task follows a defined path from creation to completion:

```
[Task Created]
      ↓
  Needs_Action
      ↓
    Plans
      ↓
 Pending_Approval
      ↓
   ┌───┴───┐
Approved   Rejected
   ↓           ↓
 Done      (Review & Revise)
   ↓
  Logs
```

### Step-by-Step Flow

1. **Creation**: A new task is created and placed in `Needs_Action`.
2. **Planning**: The task is analyzed and a plan is drafted. The task file moves to `Plans`.
3. **Submission**: Once the plan is complete, the task moves to `Pending_Approval`.
4. **Review**: An approver reviews the task and makes a decision.
5. **Decision**:
   - If approved: Task moves to `Approved`.
   - If rejected: Task moves to `Rejected` with feedback.
6. **Execution**: Approved tasks are executed. Upon completion, they move to `Done`.
7. **Archival**: Completed tasks are logged in `Logs` for record-keeping.

---

## Folder Responsibilities

### Needs_Action
- **Purpose**: Holds new tasks that require attention.
- **Contents**: Unprocessed task requests, new assignments, incoming work items.
- **Exit Condition**: Task is reviewed and a plan is created.

### Plans
- **Purpose**: Holds tasks that are being planned or designed.
- **Contents**: Task files with draft plans, proposed solutions, or strategy outlines.
- **Exit Condition**: Plan is finalized and ready for approval review.

### Pending_Approval
- **Purpose**: Holds tasks awaiting review and approval.
- **Contents**: Completed plans submitted for decision.
- **Exit Condition**: Approver reviews and moves task to Approved or Rejected.

### Approved
- **Purpose**: Holds tasks that have been approved and are ready for execution.
- **Contents**: Authorized work items cleared for action.
- **Exit Condition**: Task execution is complete.

### Rejected
- **Purpose**: Holds tasks that did not pass approval.
- **Contents**: Tasks with documented rejection reasons and required revisions.
- **Exit Condition**: Task is revised and resubmitted to Pending_Approval, or permanently closed.

### Done
- **Purpose**: Holds successfully completed tasks.
- **Contents**: Finished work items with completion confirmation.
- **Exit Condition**: Task is archived to Logs.

### Logs
- **Purpose**: Permanent archive of all completed and closed tasks.
- **Contents**: Historical records of all processed tasks with outcomes and timestamps.
- **Exit Condition**: None. This is the final resting place for all task records.

---

## Approval Rules

### Who Can Approve
- Designated approvers, system administrators, or authorized decision-makers.

### Approval Criteria
A task is approved when:
- The plan is complete and addresses all requirements.
- Resources and dependencies are identified.
- Risks have been assessed and are acceptable.
- The proposed approach aligns with business goals.

### Rejection Criteria
A task is rejected when:
- The plan is incomplete or unclear.
- Requirements are not fully addressed.
- Risks are too high without mitigation.
- The approach conflicts with existing policies or goals.

### Rejection Process
1. Approver documents the reason for rejection clearly.
2. Task file is moved to `Rejected` folder.
3. Specific feedback is added to the task file.
4. Original submitter is notified.
5. Submitter may revise and resubmit to `Pending_Approval`.

### Resubmission
- Rejected tasks may be revised and resubmitted.
- Each resubmission must address all feedback points.
- There is no limit on resubmissions, but repeated rejections should trigger escalation.

---

## Logging Rules

### What Gets Logged
- All tasks that reach `Done` status.
- All tasks that are permanently closed (including unresolved rejections).
- Key decisions and approval outcomes.

### Log Entry Requirements
Each log entry must include:
- Task name or identifier
- Date created
- Date completed or closed
- Final status (Completed, Rejected-Closed, Cancelled)
- Summary of outcome
- Approver name (if applicable)

### Log Retention
- Logs are retained indefinitely for audit and reference purposes.
- Logs should not be modified after creation.
- Logs serve as the single source of truth for historical task data.

### Log Naming Convention
- Use date-based naming: `YYYY-MM-DD_TaskName.md`
- Example: `2026-02-17_Website_Redesign.md`

---

## Daily Operation Flow

### Morning Review
1. Check `Needs_Action` for new incoming tasks.
2. Prioritize tasks based on urgency and importance.
3. Assign tasks to appropriate team members or processes.

### Active Work Period
1. Move prioritized tasks from `Needs_Action` to `Plans`.
2. Develop plans for each task.
3. Submit completed plans to `Pending_Approval`.
4. Execute tasks in `Approved` folder.
5. Move completed work to `Done`.

### Approval Cycle
1. Review all items in `Pending_Approval`.
2. Make approval or rejection decisions promptly.
3. Document all decisions with clear reasoning.
4. Notify relevant parties of outcomes.

### End of Day
1. Review `Rejected` folder for items needing revision.
2. Archive completed tasks from `Done` to `Logs`.
3. Update Dashboard with current status counts.
4. Ensure no task is left without a clear next action.

### Weekly Maintenance
1. Review `Rejected` folder for stale items.
2. Escalate tasks stuck in any folder for more than 5 days.
3. Verify `Logs` accuracy and completeness.
4. Update `Business_Goals.md` if priorities have changed.

---

## Summary

This workflow ensures every task is tracked, reviewed, and documented. By following these guidelines, the Bronze Tier system maintains clarity, accountability, and a complete audit trail for all operations.

---

*Last Updated: 2026-02-17*
