# claude-slack-bot

A Slack bot that listens for `@mentions` and triggers Claude Code on your Mac Mini. Send `@claude fix this bug` from your phone or any device, and Claude Code runs locally on your Mac Mini and replies with the result.

## How it works

The bot uses Slack's **Socket Mode** — it opens a persistent WebSocket connection *from* your Mac Mini *to* Slack. No public endpoint, no port forwarding, no ngrok required. Works behind NAT, firewalls, and Tailscale.

```
Slack "@claude do this"  (from phone, MacBook, anywhere)
        ↓
  Slack delivers event over WebSocket
        ↓
  Bot on Mac Mini receives it
        ↓
  Claude Code runs locally
        ↓
  Result posted back to Slack
```

## Requirements

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) for dependency management
- [Claude Code](https://claude.ai/code) installed and on PATH (`claude --version`)
- A Slack workspace where you can create apps

## Slack App Setup

1. Go to [api.slack.com/apps](https://api.slack.com/apps) and create a new app
2. **Socket Mode** → Enable Socket Mode → generate an `xapp-...` app-level token with `connections:write` scope
3. **Event Subscriptions** → Enable Events → add `app_mention` bot event
4. **OAuth & Permissions** → add bot scopes: `app_mentions:read`, `chat:write` → install to workspace
5. Copy the `xoxb-...` Bot Token from OAuth & Permissions
6. Find your Slack User ID: click your profile → More → Copy Member ID

## Installation

```bash
# Clone or copy the project to your Mac Mini
cd ~/claude-slack-bot

# Install dependencies with uv
uv sync

# Create the logs directory
mkdir -p logs
```

## Configuration

The bot is configured entirely via environment variables:

| Variable | Required | Description |
|---|---|---|
| `SLACK_BOT_TOKEN` | ✅ | Bot token starting with `xoxb-` |
| `SLACK_APP_TOKEN` | ✅ | App-level token starting with `xapp-` |
| `SLACK_ADMIN_USER` | ✅ | Comma-separated Slack user IDs allowed to trigger the bot (e.g. `U012AB3CD`) |
| `PROJECT_PATH` | ✅ | Absolute path where Claude Code will run |
| `CLAUDE_TIMEOUT_SECONDS` | ❌ | Timeout in seconds (default: `300`) |

## Running manually

```bash
export SLACK_BOT_TOKEN=xoxb-...
export SLACK_APP_TOKEN=xapp-...
export SLACK_ADMIN_USER=U012AB3CD
export PROJECT_PATH=~/your-project

uv run claude-slack-bot
```

You should see:
```
2024-01-01T12:00:00 INFO     __main__ Starting bot | project_path=... allowed_users=...
2024-01-01T12:00:00 INFO     __main__ Bot is running, waiting for mentions...
```

Then mention your bot in Slack: `@yourbot fix the login bug`

## Running as a background service (launchd)

To have the bot start automatically on login and restart if it crashes:

```bash
# 1. Edit the plist — replace YOUR_USERNAME and fill in your tokens
nano scripts/com.claudebot.plist

# 2. Copy to LaunchAgents
cp scripts/com.claudebot.plist ~/Library/LaunchAgents/

# 3. Load it
launchctl load ~/Library/LaunchAgents/com.claudebot.plist
```

**Useful commands:**

```bash
# Check it's running (should show an entry)
launchctl list | grep claudebot

# View live logs
tail -f ~/claude-slack-bot/logs/bot.log

# Stop the bot
launchctl unload ~/Library/LaunchAgents/com.claudebot.plist

# Start it again
launchctl load ~/Library/LaunchAgents/com.claudebot.plist
```

## Development

```bash
# Install with dev dependencies
uv sync

# Lint and format
uv run ruff check src/
uv run ruff format src/

# Type check
uv run mypy src/
```

## Security

- Only users listed in `SLACK_ADMIN_USER` can trigger Claude Code — anyone else gets a rejection message
- The bot token and app token should be treated as passwords — never commit them to git
- The `.gitignore` excludes `.plist.local` and `.env` files — keep secrets out of the plist in the repo by using a local copy
- Socket Mode means no open ports on your Mac Mini

