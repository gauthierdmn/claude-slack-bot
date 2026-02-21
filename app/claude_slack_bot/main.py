import argparse
import logging
import sys

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from claude_slack_bot.bot import register_handlers
from claude_slack_bot.config import Config

DEFAULT_PROJECT_PATH: str = "/Users/gdamn/Projects/"


def _setup_logging() -> None:
    """
    Configure root logging with a timestamped format and suppress noisy Slack loggers.
    """

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        stream=sys.stdout,
    )
    # Reduce noise from Slack's internal libraries
    logging.getLogger("slack_bolt").setLevel(logging.WARNING)
    logging.getLogger("slack_sdk").setLevel(logging.WARNING)


def _parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments.

    Returns:
        argparse.Namespace: Parsed arguments containing the project path.
    """

    parser = argparse.ArgumentParser(
        description="Slack bot that triggers Claude Code via @mention",
    )
    parser.add_argument(
        "project_path",
        nargs="?",
        default=DEFAULT_PROJECT_PATH,
        help=f"working directory for Claude Code (default: {DEFAULT_PROJECT_PATH})",
    )

    return parser.parse_args()


def main() -> None:
    """
    Parse args, load configuration, create the Slack app, and start listening.
    """

    _setup_logging()
    logger: logging.Logger = logging.getLogger(__name__)
    args: argparse.Namespace = _parse_args()

    logger.info("Loading configuration from environment")

    try:
        config: Config = Config.from_env(project_path=args.project_path)
    except (OSError, ValueError) as exc:
        logger.error("Configuration error: %s", exc)
        sys.exit(1)

    logger.info(
        "Starting bot | project_path=%s allowed_users=%s",
        config.project_path,
        config.allowed_user_ids,
    )

    app = App(token=config.slack_bot_token)
    register_handlers(app, config)
    handler = SocketModeHandler(app, config.slack_app_token)

    logger.info("Bot is running, waiting for mentions...")
    handler.start()  # type: ignore[no-untyped-call]


if __name__ == "__main__":
    main()
