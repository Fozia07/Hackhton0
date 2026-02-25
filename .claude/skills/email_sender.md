# Skill: Email Sender (MCP)

## Description
Sends emails via custom MCP server after human approval.
Integrates with Gmail API for actual email delivery.

## Trigger
- Approved email request in `/Approved/`
- Command: `/send-email`

## Inputs
| Input | Type | Required | Description |
|-------|------|----------|-------------|
| to | String | Yes | Recipient email address |
| subject | String | Yes | Email subject line |
| body | String | Yes | Email body content |
| cc | Array | No | CC recipients |
| bcc | Array | No | BCC recipients |
| attachments | Array | No | Paths to attachment files |
| reply_to | String | No | Message ID if replying |

## Process

### Step 1: Pre-flight Checks
1. Verify approval exists in `/Approved/`
2. Validate email addresses
3. Check attachment sizes
4. Verify MCP server is running

### Step 2: Request Approval (if not already approved)
1. Create approval request
2. Include email preview
3. Wait for human decision

### Step 3: MCP Server Call
1. Connect to email MCP server
2. Send email request with parameters
3. Handle response

### Step 4: Delivery Confirmation
1. Verify email was sent
2. Get message ID
3. Log delivery status

### Step 5: Cleanup
1. Move approval file to `/Done/`
2. Update Dashboard.md
3. Log to daily log

## Output
| Output | Type | Description |
|--------|------|-------------|
| success | Boolean | Whether email was sent |
| message_id | String | Gmail message ID |
| sent_at | DateTime | Delivery timestamp |
| error | String | Error message if failed |

## Email Request Template

```markdown
---
type: approval_request
action: send_email
to: {recipient}
cc: [{cc_list}]
subject: {subject}
created: {ISO_timestamp}
status: pending
priority: {priority}
---

# Email Send Request

## Recipient
**To:** {to}
**CC:** {cc_list}
**BCC:** {bcc_list}

## Subject
{subject}

## Body Preview

{body_content}

## Attachments
{attachment_list_or_none}

## Approval Required

To send this email:
- Move this file to `/Approved/`

To cancel:
- Move this file to `/Rejected/`

---
*Email Sender Skill - Awaiting Approval*
```

## MCP Server Interface

### Server Configuration
```json
{
  "name": "email-mcp",
  "command": "python3",
  "args": ["mcp_servers/email_server.py"],
  "env": {
    "GMAIL_CREDENTIALS": "/secure/credentials.json"
  }
}
```

### MCP Methods

#### send_email
```json
{
  "method": "send_email",
  "params": {
    "to": "recipient@example.com",
    "subject": "Subject line",
    "body": "Email body",
    "cc": [],
    "attachments": []
  }
}
```

#### draft_email
```json
{
  "method": "draft_email",
  "params": {
    "to": "recipient@example.com",
    "subject": "Subject line",
    "body": "Email body"
  }
}
```

## Example Usage

```
Skill: email_sender
Input:
  to: "client@example.com"
  subject: "Project Update - February 2026"
  body: "Dear Client,\n\nHere is your weekly update..."
  cc: ["team@company.com"]

Output:
  success: true
  message_id: "msg_abc123xyz"
  sent_at: "2026-02-20T14:30:00Z"
```

## Error Handling

| Error | Cause | Resolution |
|-------|-------|------------|
| AUTH_FAILED | Invalid credentials | Refresh OAuth token |
| RATE_LIMITED | Too many requests | Wait and retry |
| INVALID_ADDRESS | Bad email format | Validate before sending |
| ATTACHMENT_TOO_LARGE | File > 25MB | Compress or use link |

## Safety Rules
- All emails require human approval
- Never send to new recipients without explicit approval
- Never send bulk emails (>10 recipients) without review
- Always log sent emails
- Never expose credentials in vault

## Integration
- Works with `approval_workflow` skill
- Triggered by approved email tasks
- Logs via `Dashboard.md` updates

---
*Skill Version: 1.0 | Silver Tier*
