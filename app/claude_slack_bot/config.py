from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    """
    Application configuration loaded from environment variables.

    Attributes:
        slack_bot_token (str): Bot token starting with ``xoxb-``.
        slack_app_token (str): App-level token starting with ``xapp-``.
        allowed_user_ids (frozenset[str]): Slack user IDs permitted to trigger the bot.
        project_path (str): Absolute path where Claude Code will run.
        max_turns (int): Maximum agentic turns (0 for unlimited).
        max_slack_message_length (int): Maximum characters before truncation.
        claude_model (str): Optional Claude model override.
        claude_cli_path (str): Path to the Claude CLI binary (empty to use bundled).
    """

    slack_bot_token: str
    slack_app_token: str
    allowed_user_ids: frozenset[str]
    project_path: str
    max_turns: int = 0
    max_slack_message_length: int = 2900
    claude_model: str = ""
    claude_cli_path: str = ""

    @classmethod
    def from_env(cls, project_path: str) -> Config:
        """
        Build a Config by reading environment variables and a CLI-provided project path.

        Args:
            project_path (str): Working directory where Claude Code will run.

        Returns:
            Config: A fully populated configuration instance.

        Raises:
            OSError: If a required environment variable is missing.
            ValueError: If SLACK_ALLOWED_USERS is empty.
        """

        slack_bot_token: str = _require_env("SLACK_BOT_TOKEN")
        slack_app_token: str = _require_env("SLACK_APP_TOKEN")

        user_ids: str = _require_env("SLACK_ALLOWED_USERS")
        allowed_user_ids: frozenset[str] = frozenset(
            uid.strip() for uid in user_ids.split(",") if uid.strip()
        )

        if not allowed_user_ids:
            raise ValueError("SLACK_ALLOWED_USERS must contain at least one user ID")

        max_turns: int = int(os.environ.get("CLAUDE_MAX_TURNS", "0"))
        claude_model: str = os.environ.get("CLAUDE_MODEL", "")
        claude_cli_path: str = os.environ.get("CLAUDE_CLI_PATH", "")

        return cls(
            slack_bot_token=slack_bot_token,
            slack_app_token=slack_app_token,
            allowed_user_ids=allowed_user_ids,
            project_path=os.path.expanduser(project_path),
            max_turns=max_turns,
            claude_model=claude_model,
            claude_cli_path=claude_cli_path,
        )


def _require_env(key: str) -> str:
    """
    Read and return a required environment variable.

    Args:
        key (str): The environment variable name.

    Returns:
        str: The variable's value.

    Raises:
        OSError: If the variable is unset or empty.
    """

    value: str | None = os.environ.get(key)

    if not value:
        raise OSError(f"Required environment variable '{key}' is not set")

    return value
