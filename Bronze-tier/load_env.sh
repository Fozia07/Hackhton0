#!/bin/bash
# =============================================================================
# Load Environment Variables from .env file
# Usage: source load_env.sh
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"

if [ -f "$ENV_FILE" ]; then
    echo "Loading environment variables from .env..."

    # Export each variable from .env file
    while IFS='=' read -r key value; do
        # Skip comments and empty lines
        if [[ ! "$key" =~ ^# ]] && [[ -n "$key" ]]; then
            # Remove leading/trailing whitespace
            key=$(echo "$key" | xargs)
            value=$(echo "$value" | xargs)

            if [[ -n "$key" ]] && [[ -n "$value" ]]; then
                export "$key=$value"
                echo "  Loaded: $key"
            fi
        fi
    done < "$ENV_FILE"

    echo ""
    echo "Environment variables loaded successfully!"
    echo ""
else
    echo "Error: .env file not found at $ENV_FILE"
    echo "Please create .env file with your credentials."
fi
