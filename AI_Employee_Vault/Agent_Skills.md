# AI Agent Skills Documentation

---

## Overview

This document defines the minimal set of AI Agent Skills required to operate the Bronze Tier file-based task management system. These skills enable an AI agent to read, create, update, and move tasks through the workflow.

### System Context

| Folder | Purpose |
|--------|---------|
| `/Inbox` | Entry point for new tasks |
| `/Needs_Action` | Tasks requiring processing |
| `/Plans` | Tasks being planned |
| `/Pending_Approval` | Tasks awaiting approval |
| `/Approved` | Tasks cleared for execution |
| `/Rejected` | Tasks that failed approval |
| `/Done` | Completed tasks |
| `/Logs` | Archived task records |

### Task Representation

- Each task is a file (any format)
- Each task has an associated metadata file (`.md`)
- Metadata contains: filename, status, timestamps, priority, notes

---

## Skill 1: Read_Task

### Purpose

Read and parse task metadata from a markdown file to understand the task's current state, priority, history, and requirements.

### Inputs

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `task_file_path` | String | Yes | Absolute or relative path to the task metadata file (.md) |

### Outputs

| Output | Type | Description |
|--------|------|-------------|
| `task_id` | String | Unique identifier extracted from filename |
| `original_filename` | String | Name of the original task file |
| `status` | String | Current status (pending, in_progress, completed, etc.) |
| `priority` | String | Priority level (low, medium, high, critical) |
| `source` | String | Origin of the task (inbox, manual, external) |
| `date_created` | DateTime | When the task was created |
| `date_modified` | DateTime | Last modification timestamp |
| `notes` | String | Additional notes or context |
| `current_folder` | String | Current folder location |

### Behavior

1. Locate the specified metadata file
2. Parse markdown content to extract structured fields
3. Return structured task information
4. Return error if file not found or format invalid

### Example Usage

**Scenario:** Agent needs to understand a task before processing.

```
Skill: Read_Task
Input:
  task_file_path: "/Bronze-tier/Needs_Action/report_request.txt.md"

Output:
  task_id: "report_request.txt"
  original_filename: "report_request.txt"
  status: "pending"
  priority: "medium"
  source: "inbox"
  date_created: "2026-02-17 10:30:00"
  date_modified: "2026-02-17 10:30:00"
  notes: ""
  current_folder: "Needs_Action"
```

---

## Skill 2: Update_Task_Metadata

### Purpose

Modify specific fields in a task's metadata file, such as updating status, adding notes, or recording timestamps.

### Inputs

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `task_file_path` | String | Yes | Path to the task metadata file (.md) |
| `fields_to_update` | Object | Yes | Key-value pairs of fields to modify |

### Supported Fields

| Field | Type | Description |
|-------|------|-------------|
| `status` | String | New status value |
| `priority` | String | Updated priority level |
| `notes` | String | Additional notes (append or replace) |
| `assigned_to` | String | Person or agent assigned |
| `date_modified` | DateTime | Auto-updated on any change |

### Outputs

| Output | Type | Description |
|--------|------|-------------|
| `success` | Boolean | Whether update completed successfully |
| `file_path` | String | Path to updated file |
| `fields_updated` | Array | List of fields that were changed |
| `timestamp` | DateTime | When update occurred |

### Behavior

1. Read existing metadata file
2. Validate fields to update
3. Apply changes to specified fields
4. Update `date_modified` timestamp automatically
5. Write updated content back to file
6. Return confirmation with details

### Example Usage

**Scenario:** Agent marks a task as in-progress and adds a note.

```
Skill: Update_Task_Metadata
Input:
  task_file_path: "/Bronze-tier/Needs_Action/report_request.txt.md"
  fields_to_update:
    status: "in_progress"
    notes: "Agent reviewing requirements"
    assigned_to: "AI_Agent_01"

Output:
  success: true
  file_path: "/Bronze-tier/Needs_Action/report_request.txt.md"
  fields_updated: ["status", "notes", "assigned_to", "date_modified"]
  timestamp: "2026-02-17 11:45:00"
```

---

## Skill 3: Move_Task

### Purpose

Move a task file and its associated metadata file from one workflow folder to another, representing progression through the workflow.

### Inputs

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `source_path` | String | Yes | Current path of the task file |
| `destination_folder` | String | Yes | Target folder name |
| `include_metadata` | Boolean | No | Move associated .md file (default: true) |

### Valid Destination Folders

- `Inbox`
- `Needs_Action`
- `Plans`
- `Pending_Approval`
- `Approved`
- `Rejected`
- `Done`
- `Logs`

### Outputs

| Output | Type | Description |
|--------|------|-------------|
| `success` | Boolean | Whether move completed successfully |
| `source_path` | String | Original file location |
| `destination_path` | String | New file location |
| `metadata_moved` | Boolean | Whether metadata file was also moved |
| `timestamp` | DateTime | When move occurred |

### Behavior

1. Validate source file exists
2. Validate destination folder exists and is valid
3. Move task file to destination folder
4. Move associated metadata file (if exists and include_metadata is true)
5. Update metadata file with new folder location
6. Return confirmation

### Example Usage

**Scenario:** Agent completes a task and moves it to Done.

```
Skill: Move_Task
Input:
  source_path: "/Bronze-tier/Approved/report_request.txt"
  destination_folder: "Done"
  include_metadata: true

Output:
  success: true
  source_path: "/Bronze-tier/Approved/report_request.txt"
  destination_path: "/Bronze-tier/Done/report_request.txt"
  metadata_moved: true
  timestamp: "2026-02-17 14:20:00"
```

---

## Skill 4: Create_Task

### Purpose

Create a new task entry in the system by generating both the task file and its associated metadata file.

### Inputs

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `task_name` | String | Yes | Name for the task file |
| `description` | String | Yes | Task description or content |
| `priority` | String | No | Priority level (default: "medium") |
| `source` | String | No | Origin of task (default: "manual") |
| `initial_folder` | String | No | Starting folder (default: "Inbox") |

### Priority Options

- `low`
- `medium`
- `high`
- `critical`

### Source Options

- `inbox` - Arrived via filesystem watcher
- `manual` - Created by user
- `agent` - Created by AI agent
- `external` - From external system

### Outputs

| Output | Type | Description |
|--------|------|-------------|
| `success` | Boolean | Whether creation completed |
| `task_file_path` | String | Path to created task file |
| `metadata_file_path` | String | Path to created metadata file |
| `task_id` | String | Generated task identifier |
| `timestamp` | DateTime | Creation timestamp |

### Behavior

1. Generate unique task filename
2. Create task file with description as content
3. Generate metadata markdown file with all fields
4. Place both files in specified initial folder
5. Return paths and confirmation

### Metadata File Structure

```markdown
# Task Metadata

---

**Task ID:** [generated_id]

**Original Filename:** [task_name]

**Description:** [description]

**Date Created:** [YYYY-MM-DD HH:MM:SS]

**Date Modified:** [YYYY-MM-DD HH:MM:SS]

**Priority:** [priority]

**Status:** pending

**Source:** [source]

**Assigned To:** unassigned

**Current Folder:** [initial_folder]

---

## Notes

[empty]

---

## History

| Date | Action | Details |
|------|--------|---------|
| [timestamp] | Created | Task created by [source] |

---
```

### Example Usage

**Scenario:** Agent creates a new task based on user request.

```
Skill: Create_Task
Input:
  task_name: "update_documentation"
  description: "Review and update the API documentation for v2.0"
  priority: "high"
  source: "agent"
  initial_folder: "Inbox"

Output:
  success: true
  task_file_path: "/Bronze-tier/Inbox/update_documentation.txt"
  metadata_file_path: "/Bronze-tier/Inbox/update_documentation.txt.md"
  task_id: "update_documentation"
  timestamp: "2026-02-17 09:15:00"
```

---

## Skill Interaction Patterns

### Pattern 1: Process New Task

```
1. Read_Task      -> Understand incoming task
2. Update_Task    -> Mark as in_progress
3. [Agent work]   -> Process the task
4. Update_Task    -> Add completion notes
5. Move_Task      -> Move to Done
```

### Pattern 2: Create and Route

```
1. Create_Task    -> Generate new task in Inbox
2. Read_Task      -> Analyze task requirements
3. Move_Task      -> Route to Needs_Action
4. Update_Task    -> Assign and set priority
```

### Pattern 3: Review and Approve

```
1. Read_Task      -> Review task in Pending_Approval
2. Update_Task    -> Add review notes
3. Move_Task      -> Move to Approved or Rejected
4. Update_Task    -> Record decision reason
```

---

## Error Handling

### Common Errors

| Error | Cause | Resolution |
|-------|-------|------------|
| `FILE_NOT_FOUND` | Task file does not exist | Verify path, check folder |
| `INVALID_FOLDER` | Destination not in valid list | Use valid folder name |
| `PERMISSION_DENIED` | Cannot write to location | Check file permissions |
| `INVALID_FORMAT` | Metadata file malformed | Recreate metadata file |
| `DUPLICATE_TASK` | Task name already exists | Use unique task name |

### Error Response Format

```
success: false
error_code: "[ERROR_CODE]"
error_message: "[Human-readable description]"
suggested_action: "[How to resolve]"
```

---

## Constraints

- Skills operate on local filesystem only
- No network or external service calls
- No database dependencies
- Files must be accessible to the agent process
- Metadata files must follow markdown format
- All timestamps use local system time

---

*Document Version: 1.0*
*Last Updated: 2026-02-17*
