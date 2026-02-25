# Skill: Approval Workflow

## Description
Manages the Human-in-the-Loop approval workflow for sensitive actions.
Creates approval requests, monitors for decisions, and processes approved/rejected items.

## Trigger
- When a sensitive action requires human approval
- When processing emails, payments, or social media posts
- Command: `/approve`, `/request-approval`

## Inputs
| Input | Type | Required | Description |
|-------|------|----------|-------------|
| action_type | String | Yes | Type of action (send_email, post_linkedin, payment) |
| details | Object | Yes | Action-specific details |
| priority | String | No | low, medium, high, critical (default: medium) |
| expires | DateTime | No | Expiration time for the request |

## Process

### Step 1: Create Approval Request
1. Generate unique request ID: `APPROVAL_{action_type}_{timestamp}`
2. Create markdown file in `/Pending_Approval/`
3. Include all action details in frontmatter
4. Add human-readable summary

### Step 2: Wait for Decision
1. Monitor `/Approved/` folder for moved files
2. Monitor `/Rejected/` folder for moved files
3. Check expiration time

### Step 3: Process Decision
**If Approved:**
1. Log approval to `/Logs/`
2. Trigger the corresponding action via MCP
3. Move file to `/Done/`

**If Rejected:**
1. Log rejection to `/Logs/`
2. Add rejection record to file
3. Keep in `/Rejected/` for audit

## Output
| Output | Type | Description |
|--------|------|-------------|
| request_id | String | Unique approval request ID |
| status | String | pending, approved, rejected, expired |
| decision_time | DateTime | When decision was made |
| action_result | Object | Result of triggered action |

## Approval Request Template

```markdown
---
type: approval_request
request_id: APPROVAL_{action_type}_{timestamp}
action: {action_type}
priority: {priority}
created: {ISO_timestamp}
expires: {ISO_timestamp}
status: pending
---

# Approval Request: {action_type}

## Summary
{human_readable_summary}

## Action Details
{formatted_details}

## Instructions
- **To Approve:** Move this file to `/Approved/` folder
- **To Reject:** Move this file to `/Rejected/` folder

---
*Awaiting human decision*
```

## Example Usage

```
Skill: approval_workflow
Input:
  action_type: "send_email"
  details:
    to: "client@example.com"
    subject: "Invoice #1234"
    body: "Please find attached..."
  priority: "high"

Output:
  request_id: "APPROVAL_send_email_20260220_143022"
  status: "pending"
  file_path: "/Pending_Approval/APPROVAL_send_email_20260220_143022.md"
```

## Safety Rules
- Never auto-approve payments over $100
- Never auto-approve emails to new recipients
- Never auto-approve social media posts
- All external actions require explicit human approval

---
*Skill Version: 1.0 | Silver Tier*
