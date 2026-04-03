#!/usr/bin/env python3
"""
Environment Variable Loader
Automatically loads variables from .env file

Usage:
    from utils.env_loader import load_env
    load_env()  # Call at start of script
"""

import os
from pathlib import Path


def load_env(env_file: str = None) -> bool:
    """
    Load environment variables from .env file.

    Args:
        env_file: Path to .env file (default: project root .env)

    Returns:
        True if loaded successfully, False otherwise
    """
    try:
        from dotenv import load_dotenv

        if env_file is None:
            # Find .env in project root
            current = Path(__file__).parent.parent
            env_file = current / ".env"

        if Path(env_file).exists():
            load_dotenv(env_file)
            return True
        else:
            print(f"Warning: .env file not found at {env_file}")
            return False

    except ImportError:
        # Fallback: manual loading if python-dotenv not installed
        return _manual_load_env(env_file)


def _manual_load_env(env_file: str = None) -> bool:
    """Manually load .env without python-dotenv"""
    try:
        if env_file is None:
            current = Path(__file__).parent.parent
            env_file = current / ".env"

        if not Path(env_file).exists():
            return False

        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if not line or line.startswith('#'):
                    continue

                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()

                    # Remove quotes if present
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]

                    os.environ[key] = value

        return True

    except Exception as e:
        print(f"Error loading .env: {e}")
        return False


def get_env(key: str, default: str = None) -> str:
    """Get environment variable with optional default"""
    return os.environ.get(key, default)


def require_env(*keys) -> dict:
    """
    Require multiple environment variables.
    Raises ValueError if any are missing.

    Returns:
        Dict of key-value pairs
    """
    missing = []
    values = {}

    for key in keys:
        value = os.environ.get(key)
        if not value:
            missing.append(key)
        else:
            values[key] = value

    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

    return values


# Auto-load when imported
load_env()
