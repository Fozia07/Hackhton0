# Vault Sync Setup Guide - Platinum Tier

This guide explains how to set up Git-based synchronization between Cloud and Local agents.

## Overview

The Platinum tier uses Git to sync the `AI_Employee_Vault/` folder between:
- **Cloud Agent**: Runs 24/7 on cloud VM, creates drafts
- **Local Agent**: Runs on user's machine, executes approved tasks

```
┌─────────────────┐         Git Repo          ┌─────────────────┐
│   Cloud Agent   │◄──────(GitHub/GitLab)────►│   Local Agent   │
│                 │                            │                 │
│ - Creates drafts│                            │ - Executes tasks│
│ - Email triage  │                            │ - Sends emails  │
│ - Social drafts │                            │ - Posts social  │
└─────────────────┘                            └─────────────────┘
         │                                              │
         └──────────────► AI_Employee_Vault/ ◄──────────┘
                         (synced via Git)
```

## Quick Start

### 1. Create a Private GitHub Repository

```bash
# Go to GitHub and create a new PRIVATE repository
# Name suggestion: ai-employee-vault

# DO NOT initialize with README (we'll push existing content)
```

### 2. Initialize Vault as Git Repo

```bash
cd Bronze-tier

# Option A: Use the sync script
python3 scripts/sync_vault.py --init --remote git@github.com:YOUR_USERNAME/ai-employee-vault.git

# Option B: Manual initialization
cd AI_Employee_Vault
git init
git remote add origin git@github.com:YOUR_USERNAME/ai-employee-vault.git
git add -A
git commit -m "Initial vault setup"
git push -u origin main
```

### 3. Clone on Cloud VM

```bash
# On your cloud VM
git clone git@github.com:YOUR_USERNAME/ai-employee-vault.git AI_Employee_Vault
```

### 4. Start Sync on Both Machines

```bash
# On Local machine
python3 scripts/sync_vault.py --agent-id local --interval 30

# On Cloud VM
python3 scripts/sync_vault.py --agent-id cloud --interval 60
```

## SSH Key Setup

### Generate SSH Key (if needed)

```bash
# Generate key
ssh-keygen -t ed25519 -C "vault-sync" -f ~/.ssh/id_vault

# Add to SSH config
cat >> ~/.ssh/config << 'EOF'
Host github.com
    HostName github.com
    User git
    IdentityFile ~/.ssh/id_vault
    IdentitiesOnly yes
EOF

# Copy public key
cat ~/.ssh/id_vault.pub
```

### Add to GitHub

1. Go to: https://github.com/settings/keys
2. Click "New SSH key"
3. Paste the public key
4. Click "Add SSH key"

### Test Connection

```bash
ssh -T git@github.com
# Should see: "Hi username! You've successfully authenticated..."
```

## Configuration

### Environment Variables

```bash
# Optional: Set in .bashrc or .zshrc
export VAULT_GIT_REMOTE="origin"      # Git remote name
export VAULT_SYNC_BRANCH="main"       # Branch to sync
export VAULT_AGENT_ID="local"         # Agent identifier
```

### Sync Intervals

| Agent  | Recommended Interval | Reason                          |
|--------|---------------------|----------------------------------|
| Local  | 30s                 | User wants quick feedback        |
| Cloud  | 60s                 | Less urgent, saves resources     |

## Command Reference

```bash
# Single sync cycle
python3 scripts/sync_vault.py --once

# Continuous sync (60s default)
python3 scripts/sync_vault.py

# Custom interval
python3 scripts/sync_vault.py --interval 30

# Dry run (test without git commands)
python3 scripts/sync_vault.py --dry-run

# Check sync status
python3 scripts/sync_vault.py --status

# Initialize repo
python3 scripts/sync_vault.py --init --remote <url>
```

## How It Works

### Sync Cycle

Each sync cycle performs these steps:

1. **Pull**: Fetch latest changes from remote (conflict safety)
2. **Commit**: Stage and commit local changes with timestamp
3. **Push**: Push commits to remote

```
┌────────┐     ┌────────┐     ┌────────┐
│  Pull  │────►│ Commit │────►│  Push  │
└────────┘     └────────┘     └────────┘
    │              │              │
    ▼              ▼              ▼
  Stash       Auto-message    Retry on
  changes      with agent     conflict
              ID + time
```

### Conflict Handling

The sync system handles conflicts safely:

1. **Pull-before-push**: Always pulls before pushing
2. **Auto-stash**: Stashes local changes before pull
3. **Retry logic**: If push fails, pull and retry
4. **Abort on conflict**: Stops if manual resolution needed

### Commit Messages

Commits are automatically formatted:

```
[local] Auto-sync: 3 file(s) (2024-01-15 14:30:00)
[cloud] Auto-sync: 1 file(s) (2024-01-15 14:30:30)
```

## Integration with Agents

### Cloud Agent Integration

```python
# In cloud_agent.py - sync is automatic
# Drafts saved to Pending_Approval/ are auto-synced
```

### Local Agent Integration

```python
# In local_agent.py - sync is automatic
# Approved tasks and Done/ status are auto-synced
```

### Manual Trigger

```python
# Force sync from code
from scripts.sync_vault import VaultSync

sync = VaultSync(agent_id="cloud")
status = sync.sync_cycle()
print(f"Sync status: {status}")
```

## Folder Sync Behavior

| Folder              | Synced? | Notes                          |
|---------------------|---------|--------------------------------|
| Needs_Action/       | Yes     | New tasks                      |
| Pending_Approval/   | Yes     | Drafts for review              |
| Approved/           | Yes     | Ready to execute               |
| Done/               | Yes     | Completed tasks                |
| In_Progress/cloud/  | Yes     | Cloud's claimed tasks          |
| In_Progress/local/  | Yes     | Local's claimed tasks          |
| Updates/            | Yes     | Agent communication            |
| Signals/            | Yes     | Inter-agent signals            |
| Logs/               | No      | Local only (recreated)         |
| .env                | No      | Never sync secrets!            |

## Troubleshooting

### "Vault not initialized"

```bash
python3 scripts/sync_vault.py --init --remote <your-repo-url>
```

### "Permission denied (publickey)"

```bash
# Check SSH key
ssh -T git@github.com

# If fails, regenerate and add key to GitHub
ssh-keygen -t ed25519 -f ~/.ssh/id_vault
cat ~/.ssh/id_vault.pub
# Add to GitHub settings
```

### "Push rejected - remote has new changes"

```bash
# Pull first
cd AI_Employee_Vault
git pull --rebase origin main
git push origin main
```

### Merge Conflicts

```bash
cd AI_Employee_Vault
git status  # See conflicted files
# Edit files to resolve conflicts
git add .
git commit -m "Resolve conflicts"
git push
```

### Sync Too Slow

- Reduce interval: `--interval 15`
- Check network latency to GitHub
- Consider using a closer git server

## Security Considerations

1. **Private Repository**: Always use a private repo
2. **No Secrets**: .gitignore excludes .env, tokens, keys
3. **SSH Keys**: Use deploy keys for cloud VM
4. **Audit Logs**: All changes tracked in git history

## Running as a Service

### Linux (systemd)

Create `/etc/systemd/system/vault-sync.service`:

```ini
[Unit]
Description=AI Employee Vault Sync
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/Bronze-tier
ExecStart=/usr/bin/python3 scripts/sync_vault.py --agent-id cloud --interval 60
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable vault-sync
sudo systemctl start vault-sync
sudo systemctl status vault-sync
```

### Windows (Task Scheduler)

1. Open Task Scheduler
2. Create Basic Task: "Vault Sync"
3. Trigger: At startup
4. Action: Start a program
   - Program: `python`
   - Arguments: `scripts/sync_vault.py --agent-id local --interval 30`
   - Start in: `C:\path\to\Bronze-tier`

## Test Steps

See `docs/VAULT_SYNC_TEST.md` for verification steps.
