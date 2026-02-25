# AI Task Flow System

---

## Overview

This document defines the deterministic task processing flow for the Bronze Tier AI Agent. It establishes clear rules for how the AI reads, processes, and completes tasks using the file-based workflow system.

### Workflow Path

```
/Inbox → /Needs_Action → /Done
```

### Core Components

| Component | Description |
|-----------|-------------|
| Task File | The original file containing task content |
| Metadata File | Markdown file with task state and history |
| Workflow Folders | Directories representing task stages |
| AI Agent | Automated processor following these rules |

---

## 1. AI Operating Principles

### Core Rules

The AI agent must always follow these fundamental rules:

| Rule | Description |
|------|-------------|
| **R1: Read Before Act** | Never modify a task without first reading its metadata |
| **R2: One Task at a Time** | Process tasks sequentially, complete one before starting another |
| **R3: Always Update State** | Every action must be reflected in metadata |
| **R4: Never Delete** | Move files, never delete them (archive to Logs if needed) |
| **R5: Log Everything** | Record all decisions and actions in task history |
| **R6: Fail Gracefully** | On error, mark task as blocked, do not crash |

### Safety Constraints

| Constraint | Enforcement |
|------------|-------------|
| **S1: No External Calls** | Agent operates only on local filesystem |
| **S2: No Arbitrary Execution** | Agent cannot execute files or run commands from task content |
| **S3: Scope Limitation** | Agent only operates within Bronze-tier directory |
| **S4: No Overwrites** | Never overwrite files without backup or confirmation |
| **S5: Timeout Limit** | Single task processing must not exceed defined timeout |

### Consistency Rules

| Rule | Requirement |
|------|-------------|
| **C1: Atomic Operations** | File move and metadata update must happen together |
| **C2: State Accuracy** | Metadata folder field must match actual file location |
| **C3: Timestamp Integrity** | All timestamps use consistent format (YYYY-MM-DD HH:MM:SS) |
| **C4: Status Validity** | Status must be from defined list only |

### Valid Status Values

```
pending
in_progress
completed
blocked
deferred
needs_clarification
```

---

## 2. Task Processing Pipeline

### Pipeline Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    TASK PROCESSING PIPELINE                  │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   [SCAN]                                                     │
│      ↓                                                       │
│   [READ] ──→ Error? ──→ [HANDLE_ERROR]                      │
│      ↓                                                       │
│   [VALIDATE] ──→ Invalid? ──→ [MARK_BLOCKED]                │
│      ↓                                                       │
│   [DECIDE] ──→ Unclear? ──→ [REQUEST_CLARIFICATION]         │
│      ↓                                                       │
│   [EXECUTE] ──→ Failed? ──→ [HANDLE_FAILURE]                │
│      ↓                                                       │
│   [COMPLETE]                                                 │
│      ↓                                                       │
│   [MOVE_TO_DONE]                                            │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Step-by-Step Process

#### Step 1: SCAN

| Action | Details |
|--------|---------|
| Purpose | Find tasks to process |
| Location | `/Needs_Action` folder |
| Method | List all `.md` metadata files |
| Output | Queue of task file paths |
| Priority | Process highest priority first, then oldest |

**Scan Logic:**
```
1. List all files in /Needs_Action
2. Filter for .md metadata files
3. Sort by: priority (desc), then date_created (asc)
4. Return first task for processing
```

#### Step 2: READ

| Action | Details |
|--------|---------|
| Purpose | Load and parse task metadata |
| Input | Metadata file path |
| Method | Parse markdown to extract fields |
| Output | Structured task object |
| On Error | Go to HANDLE_ERROR |

**Required Fields to Extract:**
```
- task_id
- original_filename
- status
- priority
- description
- date_created
- notes
```

#### Step 3: VALIDATE

| Action | Details |
|--------|---------|
| Purpose | Verify task is processable |
| Checks | File exists, status is valid, not already completed |
| Output | Valid or Invalid determination |
| On Invalid | Go to MARK_BLOCKED |

**Validation Checklist:**
```
[ ] Metadata file is parseable
[ ] Original task file exists
[ ] Status is "pending" or "in_progress"
[ ] Required fields are present
[ ] Priority is valid value
```

#### Step 4: DECIDE

| Action | Details |
|--------|---------|
| Purpose | Determine action to take |
| Input | Validated task data |
| Method | Apply decision logic (see Section 3) |
| Output | Decision: execute, clarify, defer, or block |

#### Step 5: EXECUTE

| Action | Details |
|--------|---------|
| Purpose | Process the task |
| Pre-action | Update status to "in_progress" |
| Method | Task-specific processing |
| Post-action | Record results in notes |
| On Failure | Go to HANDLE_FAILURE |

#### Step 6: COMPLETE

| Action | Details |
|--------|---------|
| Purpose | Finalize task processing |
| Actions | Update status to "completed", add completion timestamp |
| Output | Updated metadata file |

#### Step 7: MOVE_TO_DONE

| Action | Details |
|--------|---------|
| Purpose | Transition task to completed folder |
| Source | `/Needs_Action` |
| Destination | `/Done` |
| Files Moved | Both task file and metadata file |
| Post-move | Update folder field in metadata |

---

## 3. Decision Logic

### Decision Matrix

| Condition | Decision | Action |
|-----------|----------|--------|
| Task is clear and actionable | EXECUTE | Process immediately |
| Task requires more information | CLARIFY | Request clarification |
| Task depends on external event | DEFER | Move to deferred status |
| Task cannot be processed | BLOCK | Mark as blocked |

### Immediate Execution Criteria

Execute the task immediately when ALL of these are true:

```
[ ] Task description is clear and specific
[ ] No external dependencies identified
[ ] Required resources are available
[ ] Task is within agent capabilities
[ ] No blocking conditions exist
```

### Request Clarification Criteria

Request clarification when ANY of these are true:

```
[ ] Task description is ambiguous
[ ] Multiple interpretations are possible
[ ] Critical information is missing
[ ] Conflicting instructions detected
[ ] Scope is undefined
```

**Clarification Action:**
```
1. Update status to "needs_clarification"
2. Add note explaining what is unclear
3. Add note with specific questions
4. Do NOT move file
5. Proceed to next task
```

### Defer Task Criteria

Defer the task when ANY of these are true:

```
[ ] Task has future date requirement
[ ] Depends on another task not yet complete
[ ] Waiting for external input
[ ] Resource temporarily unavailable
```

**Defer Action:**
```
1. Update status to "deferred"
2. Add note with defer reason
3. Add note with expected resume condition
4. Do NOT move file
5. Proceed to next task
```

### Mark Blocked Criteria

Block the task when ANY of these are true:

```
[ ] Task file is missing or corrupted
[ ] Metadata is incomplete or invalid
[ ] Unresolvable conflict detected
[ ] Task exceeds agent capabilities
[ ] Repeated failures (3+ attempts)
```

**Block Action:**
```
1. Update status to "blocked"
2. Add note with block reason
3. Add note with suggested resolution
4. Do NOT move file
5. Proceed to next task
```

### Decision Flowchart

```
START
  │
  ▼
Is task description clear?
  │
  ├── NO → REQUEST_CLARIFICATION
  │
  ▼ YES
Are all dependencies met?
  │
  ├── NO → Is dependency time-based?
  │         ├── YES → DEFER
  │         └── NO → BLOCK
  │
  ▼ YES
Is task within capabilities?
  │
  ├── NO → BLOCK
  │
  ▼ YES
Are resources available?
  │
  ├── NO → DEFER
  │
  ▼ YES
EXECUTE
```

---

## 4. Folder Transition Rules

### Allowed Transitions

| From | To | Condition |
|------|----|-----------|
| Inbox | Needs_Action | File detected by watcher (automatic) |
| Needs_Action | Done | Task completed successfully |
| Needs_Action | Needs_Action | Status update only (no move) |

### Transition: Needs_Action → Done

**Trigger:** Task processing completed successfully

**Requirements:**
```
[ ] Task execution completed without error
[ ] Status is set to "completed"
[ ] Completion timestamp recorded
[ ] All notes and history updated
```

**Procedure:**
```
1. Verify task status is "completed"
2. Move task file to /Done
3. Move metadata file to /Done
4. Update metadata: current_folder = "Done"
5. Log transition in history
```

### Transition Rules

| Rule | Description |
|------|-------------|
| **T1: Both Files Move** | Task file and metadata always move together |
| **T2: Update After Move** | Metadata folder field updated after successful move |
| **T3: No Backwards** | Tasks do not move backwards in workflow |
| **T4: Atomic Move** | If either file fails to move, rollback both |

### Files That Do Not Move

These statuses keep tasks in `/Needs_Action`:

| Status | Reason |
|--------|--------|
| `in_progress` | Currently being processed |
| `needs_clarification` | Waiting for human input |
| `deferred` | Waiting for condition to be met |
| `blocked` | Cannot be processed |

---

## 5. Status Update Rules

### When to Update Status

| Event | Status Change |
|-------|---------------|
| Agent begins reading task | No change |
| Agent begins processing | `pending` → `in_progress` |
| Processing completes successfully | `in_progress` → `completed` |
| Clarification needed | Any → `needs_clarification` |
| Task deferred | Any → `deferred` |
| Unrecoverable error | Any → `blocked` |

### Metadata Update Procedure

**Every status update must include:**

```
1. New status value
2. Updated date_modified timestamp
3. History entry with:
   - Date
   - Previous status
   - New status
   - Reason for change
```

### Update Format

```markdown
## Status Change Record

**Previous Status:** [old_status]
**New Status:** [new_status]
**Changed At:** [YYYY-MM-DD HH:MM:SS]
**Reason:** [description]
```

### History Log Entry Format

```markdown
| [YYYY-MM-DD HH:MM:SS] | [ACTION] | [DETAILS] |
```

### Mandatory Update Points

| Point | Update Required |
|-------|-----------------|
| Before processing starts | Status → in_progress |
| After processing ends | Status → completed |
| On any decision | Add note with reasoning |
| On any error | Status → blocked + error note |
| On any move | Update current_folder field |

---

## 6. Failure Handling

### Failure Types

| Type | Code | Description |
|------|------|-------------|
| File Corrupted | F1 | Cannot read or parse file |
| Metadata Missing | F2 | No .md file for task |
| Metadata Invalid | F3 | Missing required fields |
| File Not Found | F4 | Task file does not exist |
| Move Failed | F5 | Cannot move file to destination |
| Processing Error | F6 | Error during task execution |
| Conflict | F7 | Conflicting state detected |

### Failure Response Matrix

| Failure | Immediate Action | Status | Recovery |
|---------|------------------|--------|----------|
| F1: Corrupted | Log error, skip task | blocked | Manual repair needed |
| F2: Missing Metadata | Create minimal metadata | blocked | Human review needed |
| F3: Invalid Metadata | Log missing fields | blocked | Human repair needed |
| F4: File Not Found | Log warning | blocked | Human investigation |
| F5: Move Failed | Rollback, retry once | unchanged | If retry fails, block |
| F6: Processing Error | Log error details | blocked | Human review needed |
| F7: Conflict | Log conflict details | blocked | Human resolution |

### Failure Handling Procedure

```
ON FAILURE:
  1. CATCH the error
  2. LOG error type and details
  3. UPDATE task status to "blocked"
  4. ADD note with:
     - Error code
     - Error message
     - Timestamp
     - Suggested resolution
  5. DO NOT move the file
  6. CONTINUE to next task
  7. REPORT failure in daily log
```

### Recovery Actions by Type

#### F1: File Corrupted

```
1. Mark status as "blocked"
2. Add note: "File corrupted - cannot read content"
3. Add note: "Resolution: Manual file repair or recreation required"
4. Skip to next task
```

#### F2: Metadata Missing

```
1. Create minimal metadata file:
   - task_id: [filename]
   - status: blocked
   - date_created: [now]
   - notes: "Metadata auto-generated - original missing"
2. Add note: "Resolution: Human review required"
3. Skip to next task
```

#### F3: Metadata Invalid

```
1. Identify missing fields
2. Mark status as "blocked"
3. Add note: "Invalid metadata - missing: [field_list]"
4. Add note: "Resolution: Complete missing fields manually"
5. Skip to next task
```

#### F4: File Not Found

```
1. Mark status as "blocked"
2. Add note: "Task file not found at expected location"
3. Add note: "Resolution: Locate or recreate task file"
4. Skip to next task
```

#### F5: Move Failed

```
1. Attempt rollback (return files to original location)
2. Retry move once
3. If retry fails:
   - Mark status as "blocked"
   - Add note: "File move failed - permission or path error"
   - Add note: "Resolution: Check permissions and path validity"
4. Skip to next task
```

#### F6: Processing Error

```
1. Capture error message
2. Mark status as "blocked"
3. Add note: "Processing error: [error_message]"
4. Add note: "Resolution: Review task requirements and retry"
5. Skip to next task
```

#### F7: Conflict

```
1. Identify conflict type
2. Mark status as "blocked"
3. Add note: "Conflict detected: [conflict_description]"
4. Add note: "Resolution: Human decision required"
5. Skip to next task
```

### Retry Policy

| Scenario | Max Retries | Wait Between |
|----------|-------------|--------------|
| File move | 1 | Immediate |
| File read | 2 | 1 second |
| Metadata parse | 0 | N/A |
| Processing | 0 | N/A |

---

## Quick Reference

### Processing Loop

```
LOOP:
  1. Scan /Needs_Action for tasks
  2. If no tasks, wait and repeat
  3. Select highest priority task
  4. Read metadata
  5. Validate task
  6. Make decision
  7. Execute or update status
  8. Move to /Done if completed
  9. Repeat
```

### Status Quick Reference

| Status | Can Process? | Can Move? |
|--------|--------------|-----------|
| pending | Yes | No |
| in_progress | In progress | No |
| completed | No | Yes → Done |
| blocked | No | No |
| deferred | No | No |
| needs_clarification | No | No |

### Decision Quick Reference

| Situation | Decision |
|-----------|----------|
| Clear task, no dependencies | Execute |
| Unclear task | Clarify |
| Future dependency | Defer |
| Capability exceeded | Block |
| File error | Block |

---

*Document Version: 1.0*
*Last Updated: 2026-02-17*
