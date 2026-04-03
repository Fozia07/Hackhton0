#!/bin/bash
# Platinum Tier - Cloud Agent Entrypoint
# AI Employee Hackathon

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1"
}

error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1"
}

# Configuration
VAULT_PATH="${VAULT_PATH:-/data/AI_Employee_Vault}"
SSH_PATH="${SSH_PATH:-/ssh}"
LOGS_PATH="${LOGS_PATH:-/logs}"
SYNC_INTERVAL="${SYNC_INTERVAL:-60}"
AGENT_INTERVAL="${AGENT_INTERVAL:-30}"
AGENT_ID="${VAULT_AGENT_ID:-cloud}"

# PID files for process management
SYNC_PID_FILE="/tmp/sync_vault.pid"
AGENT_PID_FILE="/tmp/cloud_agent.pid"
WATCHDOG_PID_FILE="/tmp/watchdog.pid"

# Cleanup function
cleanup() {
    log "Shutting down services..."

    # Kill processes if running
    for pid_file in $SYNC_PID_FILE $AGENT_PID_FILE $WATCHDOG_PID_FILE; do
        if [ -f "$pid_file" ]; then
            pid=$(cat "$pid_file")
            if kill -0 "$pid" 2>/dev/null; then
                log "Stopping process $pid..."
                kill "$pid" 2>/dev/null || true
            fi
            rm -f "$pid_file"
        fi
    done

    log "Cleanup complete"
    exit 0
}

# Set up signal handlers
trap cleanup SIGTERM SIGINT SIGQUIT

# Setup SSH for Git
setup_ssh() {
    log "Setting up SSH for Git..."

    # Check for SSH key
    if [ -f "$SSH_PATH/id_ed25519" ] || [ -f "$SSH_PATH/id_rsa" ]; then
        mkdir -p ~/.ssh
        cp "$SSH_PATH"/id_* ~/.ssh/ 2>/dev/null || true
        cp "$SSH_PATH"/known_hosts ~/.ssh/ 2>/dev/null || true
        chmod 700 ~/.ssh
        chmod 600 ~/.ssh/id_* 2>/dev/null || true

        # Configure SSH for GitHub
        cat > ~/.ssh/config << 'EOF'
Host github.com
    HostName github.com
    User git
    IdentityFile ~/.ssh/id_ed25519
    IdentitiesOnly yes
    StrictHostKeyChecking accept-new
EOF
        chmod 600 ~/.ssh/config

        log "SSH configured successfully"
    else
        warn "No SSH key found in $SSH_PATH"
        warn "Git sync will not work without SSH key"
    fi
}

# Setup Git configuration
setup_git() {
    log "Setting up Git configuration..."

    git config --global user.name "${GIT_USER_NAME:-AI Employee Cloud Agent}"
    git config --global user.email "${GIT_USER_EMAIL:-cloud-agent@aiemployee.local}"
    git config --global init.defaultBranch main
    git config --global pull.rebase true

    log "Git configured"
}

# Verify vault directory
verify_vault() {
    log "Verifying vault directory..."

    if [ ! -d "$VAULT_PATH" ]; then
        error "Vault directory not found: $VAULT_PATH"
        error "Please mount the vault volume or clone the repository"
        return 1
    fi

    if [ ! -d "$VAULT_PATH/.git" ]; then
        warn "Vault is not a git repository"
        warn "Run: cd $VAULT_PATH && git init"
        return 1
    fi

    log "Vault verified: $VAULT_PATH"
    return 0
}

# Create required directories
create_directories() {
    log "Creating required directories..."

    mkdir -p "$VAULT_PATH/Needs_Action"
    mkdir -p "$VAULT_PATH/Pending_Approval"
    mkdir -p "$VAULT_PATH/Approved"
    mkdir -p "$VAULT_PATH/Done"
    mkdir -p "$VAULT_PATH/In_Progress/cloud"
    mkdir -p "$VAULT_PATH/In_Progress/local"
    mkdir -p "$VAULT_PATH/Updates"
    mkdir -p "$VAULT_PATH/Signals"
    mkdir -p "$VAULT_PATH/Logs"
    mkdir -p "$LOGS_PATH"

    log "Directories created"
}

# Start vault sync
start_sync() {
    log "Starting vault sync (interval: ${SYNC_INTERVAL}s)..."

    cd /app
    python scripts/sync_vault.py \
        --agent-id "$AGENT_ID" \
        --interval "$SYNC_INTERVAL" \
        >> "$LOGS_PATH/sync_vault.log" 2>&1 &

    echo $! > "$SYNC_PID_FILE"
    log "Vault sync started (PID: $(cat $SYNC_PID_FILE))"
}

# Start cloud agent
start_agent() {
    log "Starting cloud agent (interval: ${AGENT_INTERVAL}s)..."

    cd /app

    # Set PYTHONPATH to include app directory
    export PYTHONPATH=/app:$PYTHONPATH

    # Run cloud agent in continuous mode
    python scripts/cloud_agent.py \
        --interval "$AGENT_INTERVAL" \
        >> "$LOGS_PATH/cloud_agent.log" 2>&1 &

    echo $! > "$AGENT_PID_FILE"
    log "Cloud agent started (PID: $(cat $AGENT_PID_FILE))"
}

# Start watchdog (optional)
start_watchdog() {
    log "Starting watchdog..."

    cd /app

    # Simple watchdog loop
    (
        while true; do
            # Check sync process
            if [ -f "$SYNC_PID_FILE" ]; then
                pid=$(cat "$SYNC_PID_FILE")
                if ! kill -0 "$pid" 2>/dev/null; then
                    warn "Sync process died, restarting..."
                    start_sync
                fi
            fi

            # Check agent process
            if [ -f "$AGENT_PID_FILE" ]; then
                pid=$(cat "$AGENT_PID_FILE")
                if ! kill -0 "$pid" 2>/dev/null; then
                    warn "Agent process died, restarting..."
                    start_agent
                fi
            fi

            # Write heartbeat
            echo "{\"timestamp\": \"$(date -Iseconds)\", \"agent\": \"$AGENT_ID\", \"status\": \"healthy\"}" \
                > "$VAULT_PATH/Signals/heartbeat_${AGENT_ID}.json"

            sleep 60
        done
    ) >> "$LOGS_PATH/watchdog.log" 2>&1 &

    echo $! > "$WATCHDOG_PID_FILE"
    log "Watchdog started (PID: $(cat $WATCHDOG_PID_FILE))"
}

# Main function
main() {
    log "=========================================="
    log "  AI Employee - Cloud Agent Starting"
    log "=========================================="
    log "Agent ID: $AGENT_ID"
    log "Vault Path: $VAULT_PATH"
    log "Sync Interval: ${SYNC_INTERVAL}s"
    log "Agent Interval: ${AGENT_INTERVAL}s"
    log "=========================================="

    # Setup
    setup_ssh
    setup_git
    create_directories

    # Verify vault (warn but continue)
    verify_vault || warn "Continuing without verified vault..."

    # Parse command
    case "${1:-all}" in
        sync)
            log "Running sync only..."
            start_sync
            ;;
        agent)
            log "Running agent only..."
            start_agent
            ;;
        watchdog)
            log "Running watchdog only..."
            start_watchdog
            ;;
        all)
            log "Running all services..."
            start_sync
            sleep 5  # Wait for first sync
            start_agent
            start_watchdog
            ;;
        test)
            log "Running in test mode..."
            python scripts/sync_vault.py --once --agent-id "$AGENT_ID"
            python scripts/cloud_agent.py --once --dry-run
            log "Test complete"
            exit 0
            ;;
        shell)
            log "Starting interactive shell..."
            exec /bin/bash
            ;;
        *)
            error "Unknown command: $1"
            echo "Usage: entrypoint.sh [sync|agent|watchdog|all|test|shell]"
            exit 1
            ;;
    esac

    log "All services started. Monitoring..."

    # Wait for any process to exit
    while true; do
        # Check if all processes are running
        all_running=true

        for pid_file in $SYNC_PID_FILE $AGENT_PID_FILE $WATCHDOG_PID_FILE; do
            if [ -f "$pid_file" ]; then
                pid=$(cat "$pid_file")
                if ! kill -0 "$pid" 2>/dev/null; then
                    all_running=false
                    break
                fi
            fi
        done

        if [ "$all_running" = false ]; then
            warn "A process has exited, watchdog will restart it"
        fi

        sleep 30
    done
}

# Run main
main "$@"
