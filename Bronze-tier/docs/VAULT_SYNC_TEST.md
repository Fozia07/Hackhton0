# Vault Sync Test Guide - Platinum Tier

Step-by-step verification that Cloud ↔ Local sync works correctly.

## Prerequisites

- [ ] GitHub repository created (private)
- [ ] SSH key added to GitHub
- [ ] sync_vault.py available
- [ ] Two environments ready (Cloud VM + Local machine)

## Test 1: Basic Initialization

### On Local Machine

```bash
cd Bronze-tier

# Initialize vault as git repo
python3 scripts/sync_vault.py --init --remote git@github.com:YOUR_USER/ai-employee-vault.git

# Expected output:
# [INFO] [sync] Initializing vault as git repository...
# [INFO] [sync] Created .gitignore for vault
# [INFO] [sync] Vault initialized successfully
```

### Verify

```bash
cd AI_Employee_Vault
git status
# Should show: On branch main, nothing to commit

git remote -v
# Should show your remote URL
```

## Test 2: Single Sync Cycle

```bash
cd Bronze-tier

# Create a test file
echo "Test task $(date)" > AI_Employee_Vault/Needs_Action/TEST_sync_check.md

# Run single sync
python3 scripts/sync_vault.py --once --agent-id local

# Expected output:
# [INFO] [local] === Starting sync cycle ===
# [INFO] [local] Pulling latest changes...
# [INFO] [local] Committed: [local] Auto-sync: 1 file(s) (...)
# [INFO] [local] Pushing changes to remote...
# [INFO] [local] Push completed successfully
```

### Verify on GitHub

1. Go to your repository on GitHub
2. Check that `Needs_Action/TEST_sync_check.md` exists
3. Check commit message format: `[local] Auto-sync: ...`

## Test 3: Cloud ↔ Local Round-Trip

This tests the full sync flow between two environments.

### Step 1: Create Task on Local

```bash
# On LOCAL machine
cat > AI_Employee_Vault/Needs_Action/EMAIL_test_roundtrip.md << 'EOF'
---
type: email
priority: normal
created: test
---

# Test Email Task

This is a test for round-trip sync.
EOF

# Sync
python3 scripts/sync_vault.py --once --agent-id local
```

### Step 2: Pull on Cloud (simulated)

```bash
# On CLOUD (or second terminal to simulate)
cd AI_Employee_Vault
git pull origin main

# Verify file exists
cat Needs_Action/EMAIL_test_roundtrip.md
```

### Step 3: Cloud Creates Draft

```bash
# On CLOUD - run cloud agent
python3 scripts/cloud_agent.py --once

# This creates: Pending_Approval/DRAFT_EMAIL_test_roundtrip.md

# Sync from cloud
python3 scripts/sync_vault.py --once --agent-id cloud
```

### Step 4: Pull Draft on Local

```bash
# On LOCAL
python3 scripts/sync_vault.py --once --agent-id local

# Verify draft exists
ls AI_Employee_Vault/Pending_Approval/
# Should see: DRAFT_EMAIL_test_roundtrip.md
```

### Step 5: Approve and Execute

```bash
# On LOCAL - move to Approved
mv AI_Employee_Vault/Pending_Approval/DRAFT_EMAIL_test_roundtrip.md \
   AI_Employee_Vault/Approved/

# Run local agent
python3 scripts/local_agent.py --once --dry-run

# Verify task completed
ls AI_Employee_Vault/Done/
# Should see: DRAFT_EMAIL_test_roundtrip.md
```

### Step 6: Final Sync

```bash
# Sync completed task
python3 scripts/sync_vault.py --once --agent-id local

# On CLOUD - pull and verify
cd AI_Employee_Vault
git pull origin main
ls Done/
# Should see completed task
```

## Test 4: Continuous Sync

### Start Sync on Both Machines

```bash
# Terminal 1 (Local)
python3 scripts/sync_vault.py --agent-id local --interval 30

# Terminal 2 (Cloud - or second terminal)
python3 scripts/sync_vault.py --agent-id cloud --interval 30
```

### Create Files and Watch Sync

```bash
# In a third terminal
echo "Quick test $(date)" > AI_Employee_Vault/Updates/test_update.json

# Watch terminals - should see:
# [local] Committed: [local] Auto-sync: 1 file(s) ...
# [local] Push completed successfully
# ...
# [cloud] Pull completed successfully
```

## Test 5: Conflict Safety

### Simulate Concurrent Edits

```bash
# Terminal A - create file
echo "Version A" > AI_Employee_Vault/Needs_Action/CONFLICT_test.md
python3 scripts/sync_vault.py --once --agent-id local

# Terminal B - create same file (before pulling)
cd AI_Employee_Vault
echo "Version B" > Needs_Action/CONFLICT_test.md
git add .
git commit -m "Conflict test B"
git push  # This should fail or require pull
```

### Expected Behavior

The sync script should:
1. Pull first (stashing local changes)
2. Apply stashed changes
3. Handle conflict if present
4. Report conflict status in logs

## Test 6: Dry Run Mode

```bash
# Test without executing git commands
echo "Dry run test" > AI_Employee_Vault/Needs_Action/DRYRUN_test.md

python3 scripts/sync_vault.py --once --dry-run

# Should see:
# [DEBUG] [sync] [DRY-RUN] Would run: git pull --rebase origin main
# [DEBUG] [sync] [DRY-RUN] Would run: git add -A
# etc.

# File should NOT be pushed
git status AI_Employee_Vault/
# Should show untracked file
```

## Test 7: Status Check

```bash
python3 scripts/sync_vault.py --status

# Expected output (JSON):
# {
#   "initialized": true,
#   "changes": [],
#   "untracked": ["Needs_Action/some_file.md"],
#   "staged": [],
#   "conflicts": []
# }
```

## Test 8: Signal/Update Sync

### Test Signals Folder

```bash
# On Cloud - create signal
cat > AI_Employee_Vault/Signals/test_signal.json << 'EOF'
{
  "signal_id": "test-123",
  "signal_type": "approval_needed",
  "from_agent": "cloud",
  "to_agent": "local",
  "created_at": "2024-01-15T10:00:00",
  "payload": {"task": "EMAIL_test.md"}
}
EOF

# Sync
python3 scripts/sync_vault.py --once --agent-id cloud
```

### Verify on Local

```bash
# Pull on local
python3 scripts/sync_vault.py --once --agent-id local

# Check signal received
cat AI_Employee_Vault/Signals/test_signal.json
```

## Test 9: .gitignore Verification

### These Should NOT Sync

```bash
# Create files that should be ignored
echo "SECRET" > AI_Employee_Vault/.env
echo "LOG" > AI_Employee_Vault/Logs/test.log
touch AI_Employee_Vault/Logs/sync_status.json

# Check git status
cd AI_Employee_Vault
git status

# These should NOT appear as untracked:
# .env
# Logs/test.log
# Logs/sync_status.json
```

### These SHOULD Sync

```bash
# Create files that should sync
echo "task" > AI_Employee_Vault/Needs_Action/real_task.md
echo "draft" > AI_Employee_Vault/Pending_Approval/real_draft.md

# Check git status
git status

# These SHOULD appear as untracked:
# Needs_Action/real_task.md
# Pending_Approval/real_draft.md
```

## Test 10: Full Platinum Flow

This is the complete end-to-end test.

```bash
# 1. Start continuous sync (both machines)
python3 scripts/sync_vault.py --agent-id local --interval 30 &
# (On cloud): python3 scripts/sync_vault.py --agent-id cloud --interval 30 &

# 2. Create email task
cat > AI_Employee_Vault/Needs_Action/EMAIL_platinum_test.md << 'EOF'
---
type: email
priority: high
from: customer@example.com
---
# Customer Inquiry
Please respond to this customer inquiry.
EOF

# 3. Wait for sync (30s)
sleep 35

# 4. Run cloud agent (creates draft)
python3 scripts/cloud_agent.py --once

# 5. Wait for sync
sleep 35

# 6. Check draft appeared locally
ls AI_Employee_Vault/Pending_Approval/
# Should see: DRAFT_EMAIL_platinum_test.md

# 7. Approve (simulate user action)
mv AI_Employee_Vault/Pending_Approval/DRAFT_EMAIL_platinum_test.md \
   AI_Employee_Vault/Approved/

# 8. Run local agent (executes)
python3 scripts/local_agent.py --once --dry-run

# 9. Verify completion
ls AI_Employee_Vault/Done/
# Should see: DRAFT_EMAIL_platinum_test.md

# 10. Stop sync
pkill -f sync_vault.py
```

## Cleanup

```bash
# Remove test files
rm -f AI_Employee_Vault/Needs_Action/TEST_*.md
rm -f AI_Employee_Vault/Needs_Action/EMAIL_test*.md
rm -f AI_Employee_Vault/Needs_Action/CONFLICT_*.md
rm -f AI_Employee_Vault/Needs_Action/DRYRUN_*.md
rm -f AI_Employee_Vault/Done/DRAFT_EMAIL_test*.md
rm -f AI_Employee_Vault/Signals/test_signal.json
rm -f AI_Employee_Vault/Updates/test_update.json

# Sync cleanup
python3 scripts/sync_vault.py --once
```

## Success Criteria

| Test | Expected Result | Status |
|------|-----------------|--------|
| 1. Init | Vault becomes git repo | [ ] |
| 2. Single Sync | File pushed to GitHub | [ ] |
| 3. Round-trip | File appears on both machines | [ ] |
| 4. Continuous | Auto-sync every N seconds | [ ] |
| 5. Conflict | Handled safely, no data loss | [ ] |
| 6. Dry Run | No actual git operations | [ ] |
| 7. Status | JSON output with state | [ ] |
| 8. Signals | JSON files sync correctly | [ ] |
| 9. .gitignore | Secrets excluded | [ ] |
| 10. Full Flow | End-to-end success | [ ] |

## Troubleshooting

### Sync Not Starting

```bash
# Check if vault is initialized
python3 scripts/sync_vault.py --status

# If not initialized:
python3 scripts/sync_vault.py --init --remote <url>
```

### Push Failures

```bash
# Manual fix
cd AI_Employee_Vault
git pull --rebase origin main
git push origin main
```

### Permission Errors

```bash
# Check SSH
ssh -T git@github.com

# Re-add key if needed
cat ~/.ssh/id_*.pub
# Add to GitHub settings
```
