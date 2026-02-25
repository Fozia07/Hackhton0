# Skill: Gmail Watcher

## Description
Monitors Gmail inbox for new emails, filters important messages,
and creates task files in the vault for processing.

## Trigger
- Runs continuously as background watcher
- Polls Gmail API every 2 minutes
- Command: `/watch-gmail`, `/check-email`

## Inputs
| Input | Type | Required | Description |
|-------|------|----------|-------------|
| credentials_path | String | Yes | Path to Gmail API credentials |
| filter_labels | Array | No | Labels to monitor (default: INBOX, IMPORTANT) |
| keywords | Array | No | Keywords to flag as urgent |
| check_interval | Integer | No | Seconds between checks (default: 120) |

## Process

### Step 1: Authentication
1. Load Gmail API credentials from secure location
2. Authenticate using OAuth 2.0
3. Verify access token is valid

### Step 2: Fetch New Emails
1. Query Gmail API for unread messages
2. Filter by labels: INBOX, IMPORTANT, UNREAD
3. Get message metadata and snippet

### Step 3: Analyze & Prioritize
1. Check sender against known contacts
2. Scan subject/body for urgent keywords
3. Assign priority: critical, high, medium, low

### Step 4: Create Task Files
1. Generate task file in `/Inbox/email/`
2. Include email metadata in frontmatter
3. Add suggested actions

### Step 5: Notify
1. Update Dashboard.md with new email count
2. Log activity to daily log

## Output
| Output | Type | Description |
|--------|------|-------------|
| emails_processed | Integer | Number of new emails found |
| tasks_created | Array | List of created task files |
| high_priority | Integer | Count of urgent emails |

## Email Task Template

```markdown
---
type: email
email_id: {gmail_message_id}
from: {sender_email}
to: {recipient}
subject: {subject}
received: {ISO_timestamp}
priority: {priority}
status: pending
labels: [{labels}]
---

# Email: {subject}

## From
{sender_name} <{sender_email}>

## Received
{formatted_date}

## Preview
{email_snippet}

## Suggested Actions
- [ ] Reply to sender
- [ ] Forward to relevant party
- [ ] Create follow-up task
- [ ] Archive after processing

---
*Detected by Gmail Watcher*
```

## Keywords for Priority Detection

### Critical Keywords
- urgent, asap, emergency, critical, immediately

### High Priority Keywords
- important, priority, deadline, invoice, payment

### Business Keywords
- proposal, contract, meeting, client, project

## Example Usage

```
Skill: gmail_watcher
Input:
  credentials_path: "/secure/gmail_credentials.json"
  filter_labels: ["INBOX", "IMPORTANT"]
  keywords: ["urgent", "invoice", "payment"]
  check_interval: 120

Output:
  emails_processed: 3
  tasks_created: [
    "/Inbox/email/EMAIL_abc123.md",
    "/Inbox/email/EMAIL_def456.md",
    "/Inbox/email/EMAIL_ghi789.md"
  ]
  high_priority: 1
```

## Gmail API Setup Required

1. Create Google Cloud Project
2. Enable Gmail API
3. Create OAuth 2.0 credentials
4. Download credentials.json
5. Store securely (never in vault)

## Safety Rules
- Never store credentials in vault
- Never auto-reply without approval
- Mark sensitive emails for human review
- Log all email access for audit

---
*Skill Version: 1.0 | Silver Tier*
