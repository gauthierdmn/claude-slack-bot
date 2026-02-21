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
        claude_timeout_seconds (int): Subprocess timeout in seconds.
        max_slack_message_length (int): Maximum characters before truncation.
    """

    slack_bot_token: str
    slack_app_token: str
    allowed_user_ids: frozenset[str]
    project_path: str
    claude_timeout_seconds: int = 300
    max_slack_message_length: int = 2900

    @classmethod
    def from_env(cls, project_path: str) -> "Config":
        """
        Build a Config by reading environment variables and a CLI-provided project path.

        Args:
            project_path (str): Working directory where Claude Code will run.

        Returns:
            Config: A fully populated configuration instance.

        Raises:
            OSError: If a required environment variable is missing.
            ValueError: If SLACK_ADMIN_USER is empty.
        """

        slack_bot_token = _require_env("SLACK_BOT_TOKEN")
        slack_app_token = _require_env("SLACK_APP_TOKEN")

        raw_user_ids = _require_env("SLACK_ADMIN_USER")
        allowed_user_ids = frozenset(
            uid.strip() for uid in raw_user_ids.split(",") if uid.strip()
        )

        if not allowed_user_ids:
            raise ValueError("SLACK_ADMIN_USER must contain at least one user ID")

        timeout = int(os.environ.get("CLAUDE_TIMEOUT_SECONDS", "300"))

        return cls(
            slack_bot_token=slack_bot_token,
            slack_app_token=slack_app_token,
            allowed_user_ids=allowed_user_ids,
            project_path=os.path.expanduser(project_path),
            claude_timeout_seconds=timeout,
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

    value = os.environ.get(key)

    if not value:
        raise OSError(f"Required environment variable '{key}' is not set")

    return value
