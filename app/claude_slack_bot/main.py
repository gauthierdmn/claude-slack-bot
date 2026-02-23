import argparse
import asyncio
import logging
import sys

from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp

from claude_slack_bot.bot import register_handlers
from claude_slack_bot.config import Config
from claude_slack_bot.session import SessionQueue, SessionStore


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
    logging.getLogger("slack_bolt").setLevel(logging.WARNING)
    logging.getLogger("slack_sdk").setLevel(logging.WARNING)


def _parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments.

    Returns:
        argparse.Namespace: Parsed arguments containing the project path.
    """

    parser = argparse.ArgumentParser(
        description="Slack bot that triggers Claude Code via @mention or message",
    )
    parser.add_argument(
        "project_path",
        nargs="?",
        default="~",
        help="working directory for Claude Code (default: ~/)",
    )

    return parser.parse_args()


async def _async_main() -> None:
    """
    Async core: create the Slack app, register handlers, and start listening.
    """

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

    session_store: SessionStore = SessionStore()
    session_queue: SessionQueue = SessionQueue()
    app: AsyncApp = AsyncApp(token=config.slack_bot_token)
    register_handlers(app, config, session_store, session_queue)
    handler: AsyncSocketModeHandler = AsyncSocketModeHandler(
        app, config.slack_app_token,
    )

    logger.info("Bot is running, waiting for mentions...")

    try:
        await handler.start_async()  # type: ignore[no-untyped-call]
    except asyncio.CancelledError:
        pass
    finally:
        logger.info("Shutting down...")
        await handler.close_async()  # type: ignore[no-untyped-call]


def main() -> None:
    """
    Parse args, load configuration, create the async Slack app, and start listening.
    """

    _setup_logging()

    try:
        asyncio.run(_async_main())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
