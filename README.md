# claude-slack-bot

A Slack bot that triggers Claude Code via `@mentions` in channels or direct messages. Send `@claude fix this bug` from your phone or any device, and Claude Code runs on your server and replies with the result.

## How it works

The bot uses Slack's **Socket Mode** — it opens a persistent WebSocket connection *from* your machine *to* Slack. No public endpoint, no port forwarding. Works behind NAT, firewalls, and Tailscale.

```
Slack "@claude do this"  (from phone, laptop, anywhere)
        ↓
  Slack delivers event over WebSocket
        ↓
  Bot receives it
        ↓
  Claude Code runs locally
        ↓
  Result posted back to Slack
```

## Requirements

- Python 3.13+
- [uv](https://github.com/astral-sh/uv) for dependency management
- [Claude Code](https://claude.ai/code) installed and on PATH (`claude --version`)
- A Slack workspace where you can create apps

## Slack App Setup

1. Go to [api.slack.com/apps](https://api.slack.com/apps) and create a new app (from scratch)
2. **Socket Mode** → Enable Socket Mode → generate an `xapp-...` app-level token with `connections:write` scope
3. **App Home** → enable the **Messages Tab** (required for DMs to work)
4. **Event Subscriptions** → Enable Events → subscribe to bot events: `app_mention`, `message.im`
5. **OAuth & Permissions** → add bot scopes: `app_mentions:read`, `chat:write`, `im:history`, `im:read`, `reactions:write` → install to workspace
6. Copy the `xoxb-...` Bot Token from OAuth & Permissions
7. Find your Slack User ID: click your profile → More → Copy Member ID

## Installation

```bash
# Clone the project
cd ~/claude-slack-bot

# Install dependencies with uv
uv sync

# Create the logs directory
mkdir -p logs
```

## Configuration

The bot is configured entirely via environment variables:

| Variable           | Required | Description |
|--------------------|----------|------------------------------------------------------------------------|
| `SLACK_BOT_TOKEN`  | ✅ | Bot token starting with `xoxb-`                                              |
| `SLACK_APP_TOKEN`  | ✅ | App-level token starting with `xapp-`                                        |
| `SLACK_ALLOWED_USERS` | ✅ | Comma-separated Slack user IDs allowed to trigger the bot (e.g. `U012AB3CD`) |
| `CLAUDE_MAX_TURNS` | ❌ | Maximum agentic turns (default: `0` for unlimited)                           |
| `CLAUDE_MODEL`     | ❌ | Claude model override (e.g. `claude-sonnet-4-6`)                             |
| `CLAUDE_CLI_PATH`  | ❌ | Path to the Claude CLI binary (default: bundled)                             |

## Running manually

```bash
export SLACK_BOT_TOKEN=xoxb-...
export SLACK_APP_TOKEN=xapp-...
export SLACK_ALLOWED_USERS=U012AB3CD

uv run claude-slack-bot ~/your-project
```

You should see:
```
2024-01-01T12:00:00 INFO     __main__ Starting bot | project_path=... allowed_users=...
2024-01-01T12:00:00 INFO     __main__ Bot is running, waiting for mentions...
```

Then mention your bot in a channel (`@yourbot fix the login bug`) or send it a direct message.

## Running with the wrapper script

A convenience script is included at `scripts/run.sh`. It activates the virtualenv, validates required env vars, and forwards arguments to the bot:

```bash
export SLACK_BOT_TOKEN=xoxb-...
export SLACK_APP_TOKEN=xapp-...
export SLACK_ALLOWED_USERS=U012AB3CD

./scripts/run.sh ~/your-project
```

## Development

```bash
# Install with dev dependencies
uv sync

# Lint and format
uv run ruff check app/ tests/
uv run ruff format app/ tests/

# Type check
uv run mypy app/

# Run tests
uv run pytest
```

## Security

- Only users listed in `SLACK_ALLOWED_USERS` can trigger Claude Code — anyone else gets a rejection message
- The bot token and app token should be treated as passwords — never commit them to git
- Socket Mode means no open ports on your machine
