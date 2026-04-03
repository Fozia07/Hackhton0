# Cloud VM Setup Guide - Platinum Tier

Complete guide to deploying the AI Employee Cloud Agent on a cloud VM.

## Overview

The Cloud Agent runs 24/7 on a VM and:
- Monitors vault for new tasks
- Creates drafts (emails, social posts)
- Syncs with local via Git
- Auto-restarts on failure

```
┌──────────────────────────────────────────────────────────────┐
│                    CLOUD VM (Oracle/AWS/etc)                  │
├──────────────────────────────────────────────────────────────┤
│  Docker Container                                             │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐ │  │
│  │  │ cloud_agent │  │ sync_vault  │  │    watchdog     │ │  │
│  │  │   (30s)     │  │   (60s)     │  │     (60s)       │ │  │
│  │  └─────────────┘  └─────────────┘  └─────────────────┘ │  │
│  └────────────────────────────────────────────────────────┘  │
│                             │                                 │
│                             ▼                                 │
│  ┌────────────────────────────────────────────────────────┐  │
│  │                  AI_Employee_Vault/                     │  │
│  │               (Git-synced with Local)                   │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

## Quick Start (5 Minutes)

```bash
# 1. SSH into your VM
ssh user@your-vm-ip

# 2. Clone this repo
git clone https://github.com/YOUR_USER/Hackhton0.git
cd Hackhton0/Bronze-tier/deploy

# 3. Setup
./setup-vm.sh  # or follow manual steps below

# 4. Start
docker-compose up -d

# 5. Verify
docker-compose ps
docker-compose logs -f
```

## Part 1: Create Cloud VM

### Option A: Oracle Cloud (Free Tier)

Oracle offers a generous free tier with ARM-based VMs.

1. **Create Account**: https://cloud.oracle.com
2. **Create VM Instance**:
   - Shape: `VM.Standard.A1.Flex` (Free tier: 4 OCPUs, 24GB RAM)
   - Or: `VM.Standard.E2.1.Micro` (Always Free x86)
   - Image: Ubuntu 22.04
   - Network: Create VCN with public subnet
   - SSH Key: Upload your public key

3. **Security List Rules**:
   - Ingress: SSH (22), HTTP (80), HTTPS (443)
   - Egress: All protocols

4. **Get Public IP**: Note the public IP address

### Option B: AWS EC2

```bash
# Using AWS CLI
aws ec2 run-instances \
  --image-id ami-0c7217cdde317cfec \  # Ubuntu 22.04
  --instance-type t2.micro \           # Free tier
  --key-name your-key \
  --security-groups ssh-http
```

### Option C: Google Cloud

```bash
# Using gcloud CLI
gcloud compute instances create ai-employee-vm \
  --zone=us-central1-a \
  --machine-type=e2-micro \
  --image-family=ubuntu-2204-lts \
  --image-project=ubuntu-os-cloud
```

### Option D: DigitalOcean

```bash
# Using doctl CLI
doctl compute droplet create ai-employee-vm \
  --image ubuntu-22-04-x64 \
  --size s-1vcpu-1gb \
  --region nyc1 \
  --ssh-keys YOUR_KEY_ID
```

## Part 2: SSH into VM

```bash
# Basic SSH
ssh -i ~/.ssh/your-key.pem ubuntu@YOUR_VM_IP

# With SSH config (recommended)
cat >> ~/.ssh/config << 'EOF'
Host ai-employee-vm
    HostName YOUR_VM_IP
    User ubuntu
    IdentityFile ~/.ssh/your-key.pem
EOF

ssh ai-employee-vm
```

## Part 3: Install Docker

### Ubuntu 22.04

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sudo sh

# Add user to docker group (no sudo needed)
sudo usermod -aG docker $USER

# Install Docker Compose
sudo apt install -y docker-compose-plugin

# Logout and login again for group changes
exit
# SSH back in
```

### Verify Installation

```bash
docker --version
# Docker version 24.x.x

docker compose version
# Docker Compose version v2.x.x

# Test
docker run hello-world
```

## Part 4: Clone and Configure

### 4.1 Clone Repository

```bash
# Clone the main repo
git clone https://github.com/YOUR_USER/Hackhton0.git
cd Hackhton0/Bronze-tier/deploy
```

### 4.2 Setup SSH for Git Sync

The cloud agent needs SSH access to push/pull from GitHub.

```bash
# Create SSH directory
mkdir -p ~/ai-employee/ssh

# Option A: Generate new key on VM
ssh-keygen -t ed25519 -C "cloud-agent" -f ~/ai-employee/ssh/id_ed25519 -N ""

# Option B: Copy existing key from local machine
# On LOCAL machine:
scp ~/.ssh/id_ed25519_github ai-employee-vm:~/ai-employee/ssh/id_ed25519
scp ~/.ssh/id_ed25519_github.pub ai-employee-vm:~/ai-employee/ssh/id_ed25519.pub

# Show public key (add to GitHub)
cat ~/ai-employee/ssh/id_ed25519.pub
```

### 4.3 Add SSH Key to GitHub

1. Go to: https://github.com/settings/keys
2. Click "New SSH key"
3. Title: `AI-Employee-Cloud-VM`
4. Paste the public key
5. Click "Add SSH key"

### 4.4 Clone Vault Repository

```bash
# Create vault directory
mkdir -p ~/ai-employee/vault

# Clone vault repo
cd ~/ai-employee
git clone git@github.com:YOUR_USER/ai-employee-vault.git vault

# Verify
ls vault/
# Should see: Needs_Action, Pending_Approval, etc.
```

### 4.5 Configure Environment

```bash
cd ~/Hackhton0/Bronze-tier/deploy

# Copy example config
cp .env.example .env

# Edit configuration
nano .env
```

Update `.env`:

```bash
# Required paths
VAULT_PATH=/home/ubuntu/ai-employee/vault
SSH_PATH=/home/ubuntu/ai-employee/ssh
LOGS_PATH=/home/ubuntu/ai-employee/logs

# Git settings
GIT_USER_NAME=AI Employee Cloud Agent
GIT_USER_EMAIL=cloud-agent@aiemployee.local
VAULT_SYNC_BRANCH=main

# Timing (adjust as needed)
SYNC_INTERVAL=60
AGENT_INTERVAL=30

# Timezone
TZ=UTC
```

## Part 5: Build and Run

### 5.1 Build Docker Image

```bash
cd ~/Hackhton0/Bronze-tier/deploy

# Build image
docker compose build

# Or build with no cache (if issues)
docker compose build --no-cache
```

### 5.2 Start Services

```bash
# Start in background
docker compose up -d

# View logs
docker compose logs -f

# Check status
docker compose ps
```

### 5.3 Verify Running

```bash
# Check container status
docker compose ps
# NAME                STATUS          PORTS
# ai-employee-cloud   Up (healthy)

# Check logs
docker compose logs --tail=50 cloud-agent

# Check health
docker exec ai-employee-cloud python /app/healthcheck.py

# Check vault sync
ls ~/ai-employee/vault/Signals/
# Should see: heartbeat_cloud.json
```

## Part 6: Verify Sync Works

### Test from VM

```bash
# Create test task
echo "Test from cloud $(date)" > ~/ai-employee/vault/Needs_Action/TEST_cloud_task.md

# Wait for sync (60s) or trigger manually
docker exec ai-employee-cloud python /app/scripts/sync_vault.py --once

# Check GitHub - file should appear
```

### Test from Local Machine

```bash
# On LOCAL machine
cd AI_Employee_Vault
git pull origin main

# Check for cloud-created files
ls Pending_Approval/
# Should see drafts created by cloud agent
```

## Part 7: Management Commands

### Daily Operations

```bash
# View logs (live)
docker compose logs -f

# View specific service logs
docker compose logs --tail=100 cloud-agent

# Restart services
docker compose restart

# Stop services
docker compose down

# Start services
docker compose up -d

# Check health
docker compose ps
docker exec ai-employee-cloud python /app/healthcheck.py
```

### Debugging

```bash
# Enter container shell
docker exec -it ai-employee-cloud /bin/bash

# Inside container:
cd /app
python scripts/sync_vault.py --status
python scripts/cloud_agent.py --once --dry-run

# Check logs inside container
tail -f /logs/cloud_agent.log
tail -f /logs/sync_vault.log

# Exit
exit
```

### Updates

```bash
# Pull latest code
cd ~/Hackhton0
git pull origin main

# Rebuild and restart
cd Bronze-tier/deploy
docker compose build
docker compose up -d
```

## Part 8: Auto-Start on Boot

### Using systemd

```bash
# Create service file
sudo nano /etc/systemd/system/ai-employee.service
```

Add:

```ini
[Unit]
Description=AI Employee Cloud Agent
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/home/ubuntu/Hackhton0/Bronze-tier/deploy
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
User=ubuntu

[Install]
WantedBy=multi-user.target
```

Enable:

```bash
sudo systemctl enable ai-employee
sudo systemctl start ai-employee
sudo systemctl status ai-employee
```

## Part 9: Monitoring

### Option A: Dozzle (Web Log Viewer)

```bash
# Start with monitoring profile
docker compose --profile monitoring up -d

# Access at: http://YOUR_VM_IP:9999
```

### Option B: Simple Monitoring Script

```bash
# Create monitoring script
cat > ~/monitor-ai-employee.sh << 'EOF'
#!/bin/bash
while true; do
    echo "=== $(date) ==="
    docker compose -f ~/Hackhton0/Bronze-tier/deploy/docker-compose.yml ps
    docker exec ai-employee-cloud python /app/healthcheck.py 2>/dev/null || echo "Health check failed"
    echo ""
    sleep 300
done
EOF

chmod +x ~/monitor-ai-employee.sh

# Run in tmux/screen
tmux new -s monitor
~/monitor-ai-employee.sh
# Ctrl+B, D to detach
```

### Option C: Alerts (Optional)

Setup email/Slack alerts for failures using a cron job:

```bash
# Add to crontab
crontab -e
```

Add:

```
*/5 * * * * docker exec ai-employee-cloud python /app/healthcheck.py || curl -X POST "YOUR_WEBHOOK_URL" -d '{"text":"AI Employee unhealthy!"}'
```

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker compose logs

# Common issues:
# 1. Missing SSH key
ls ~/ai-employee/ssh/
# Should have: id_ed25519, id_ed25519.pub

# 2. Vault not cloned
ls ~/ai-employee/vault/
# Should have: Needs_Action, etc.

# 3. Permission issues
sudo chown -R $USER:$USER ~/ai-employee/
```

### Git Sync Fails

```bash
# Test SSH to GitHub
ssh -T git@github.com

# If fails, check key
cat ~/ai-employee/ssh/id_ed25519.pub
# Add this key to GitHub settings

# Manual sync test
cd ~/ai-employee/vault
git pull origin main
git push origin main
```

### High Memory/CPU

```bash
# Check container resources
docker stats ai-employee-cloud

# Increase limits in docker-compose.yml
# deploy:
#   resources:
#     limits:
#       memory: 1G

# Or increase sync interval to reduce load
# SYNC_INTERVAL=120
```

### Vault Out of Sync

```bash
# Force sync
cd ~/ai-employee/vault
git fetch origin
git reset --hard origin/main

# Restart container
docker compose restart
```

## Security Recommendations

1. **Firewall**: Only open ports 22 (SSH)
2. **SSH Key Auth**: Disable password auth
3. **Updates**: Keep system updated
4. **Private Repo**: Keep vault repository private
5. **Secrets**: Never commit .env or SSH keys

```bash
# Firewall (Ubuntu)
sudo ufw allow 22/tcp
sudo ufw enable

# Disable password auth
sudo nano /etc/ssh/sshd_config
# Set: PasswordAuthentication no
sudo systemctl restart sshd
```

## Cost Optimization

| Provider | Instance | Monthly Cost |
|----------|----------|--------------|
| Oracle Cloud | VM.Standard.A1.Flex | Free |
| AWS | t2.micro | ~$8.50 |
| Google Cloud | e2-micro | ~$6.11 |
| DigitalOcean | Basic Droplet | $4-6 |

Oracle Cloud Free Tier is recommended for always-free operation.
