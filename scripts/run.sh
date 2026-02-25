#!/bin/bash
# Wrapper script — activates the venv and starts the bot.
# Export the required env vars before running, or edit them below.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
APP_DIR="$PROJECT_ROOT/app"

# Activate the virtual environment managed by uv
source "$APP_DIR/.venv/bin/activate"

# Required environment variables
export SLACK_BOT_TOKEN="${SLACK_BOT_TOKEN:?SLACK_BOT_TOKEN is not set}"
export SLACK_APP_TOKEN="${SLACK_APP_TOKEN:?SLACK_APP_TOKEN is not set}"
export SLACK_ALLOWED_USERS="${SLACK_ALLOWED_USERS:?SLACK_ALLOWED_USERS is not set}"

cd "$APP_DIR"
exec python -m claude_slack_bot.main "$@"
