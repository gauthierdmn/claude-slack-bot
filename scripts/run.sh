#!/bin/bash
# Wrapper script for launchd — activates the venv and starts the bot.
# Edit the env vars below or export them from a secrets manager.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Activate the virtual environment managed by uv
source "$PROJECT_ROOT/.venv/bin/activate"

# Required environment variables
export SLACK_BOT_TOKEN="${SLACK_BOT_TOKEN:?SLACK_BOT_TOKEN is not set}"
export SLACK_APP_TOKEN="${SLACK_APP_TOKEN:?SLACK_APP_TOKEN is not set}"
export ALLOWED_SLACK_USER_IDS="${ALLOWED_SLACK_USER_IDS:?ALLOWED_SLACK_USER_IDS is not set}"
export PROJECT_PATH="${PROJECT_PATH:?PROJECT_PATH is not set}"

# Optional
export CLAUDE_TIMEOUT_SECONDS="${CLAUDE_TIMEOUT_SECONDS:-300}"

exec python -m claude_slack_bot.main

