import logging
from typing import Any

from claude_agent_sdk import CLINotFoundError
from markdown_to_mrkdwn import SlackMarkdownConverter
from slack_bolt.async_app import AsyncApp
from slack_bolt.context.say.async_say import AsyncSay

from claude_slack_bot.claude_runner import ClaudeResult, run_claude
from claude_slack_bot.config import Config
from claude_slack_bot.session import SessionQueue, SessionStore

EYES_EMOJI: str = "eyes"

logger: logging.Logger = logging.getLogger(__name__)


def register_handlers(
    app: AsyncApp,
    config: Config,
    session_store: SessionStore,
    session_queue: SessionQueue,
) -> None:
    """
    Register event handlers on the async Slack Bolt application.

    Args:
        app (AsyncApp): An async Slack Bolt app instance.
        config (Config): Application configuration.
        session_store (SessionStore): Store for mapping Slack threads
            to Claude sessions.
        session_queue (SessionQueue): Queue for serializing per-session
            Claude invocations.
    """

    async def _dispatch(
        event: dict[str, Any],
        say: AsyncSay,
        prompt: str,
    ) -> None:
        """
        Validate the user and enqueue a Claude job for the session.

        Args:
            event (dict[str, Any]): The Slack event payload.
            say (AsyncSay): Slack's say utility for posting messages.
            prompt (str): The extracted user prompt.
        """

        user_id: str = event.get("user", "")
        channel: str = event.get("channel", "")
        thread_ts: str = event.get("thread_ts", event.get("ts", ""))

        if user_id not in config.allowed_user_ids:
            logger.warning("Unauthorized message from user %s", user_id)
            await say(
                "Sorry, you're not authorized to use this bot.",
                thread_ts=thread_ts,
            )

            return

        if not prompt:
            await say(
                "Please provide a prompt after mentioning me.",
                thread_ts=thread_ts,
            )

            return

        logger.info("Received prompt from %s: %s", user_id, prompt)
        message_ts: str = event.get("ts", "")
        await _react(app, channel, message_ts, EYES_EMOJI)

        async def _job() -> None:
            await _run_claude(
                app,
                config,
                session_store,
                prompt,
                channel,
                thread_ts,
            )

        await session_queue.enqueue(channel, thread_ts, _job)

    @app.event("app_mention")
    async def handle_mention(event: dict[str, Any], say: AsyncSay) -> None:
        """
        Handle an @mention event from a channel.

        Args:
            event (dict[str, Any]): The Slack event payload.
            say (AsyncSay): Slack's say utility for posting messages.
        """

        text: str = event.get("text", "")
        prompt: str = text.split(">", 1)[-1].strip()

        await _dispatch(event, say, prompt)

    @app.event("message")
    async def handle_direct_message(event: dict[str, Any], say: AsyncSay) -> None:
        """
        Handle a direct message to the bot.

        Args:
            event (dict[str, Any]): The Slack event payload.
            say (AsyncSay): Slack's say utility for posting messages.
        """

        if event.get("channel_type") != "im":
            return

        if event.get("subtype") is not None:
            return

        prompt: str = event.get("text", "").strip()

        await _dispatch(event, say, prompt)

    return


async def _run_claude(
    app: AsyncApp,
    config: Config,
    session_store: SessionStore,
    prompt: str,
    channel: str,
    thread_ts: str,
) -> None:
    """
    Run Claude Code via the SDK and post the result back to Slack.

    Args:
        app (AsyncApp): The async Slack Bolt app instance for posting messages.
        config (Config): Application configuration.
        session_store (SessionStore): Store for mapping Slack threads
            to Claude sessions.
        prompt (str): The user's prompt to pass to Claude Code.
        channel (str): The Slack channel ID to post results in.
        thread_ts (str): The thread timestamp to reply in.
    """

    logger.info("Starting Claude Code with prompt: %s", prompt)
    existing_session: str | None = session_store.get(channel, thread_ts)

    try:
        result: ClaudeResult = await run_claude(
            prompt=prompt,
            project_path=config.project_path,
            model=config.claude_model,
            max_turns=config.max_turns,
            cli_path=config.claude_cli_path,
            session_id=existing_session or "",
        )

        if result.session_id:
            session_store.set(channel, thread_ts, result.session_id)

        response: str = _format_response(result, config.max_slack_message_length)
        logger.info("Claude finished successfully")

        await _post(app, channel, thread_ts, response)

    except CLINotFoundError:
        logger.error("Claude CLI not found — is Claude Code installed?")

        await _post(
            app,
            channel,
            thread_ts,
            "❌ Claude CLI not found. Is Claude Code installed and on PATH?",
        )
    except Exception:
        logger.exception("Unexpected error running Claude")

        await _post(
            app,
            channel,
            thread_ts,
            "❌ An unexpected error occurred. Check the bot logs.",
        )


def _format_response(result: ClaudeResult, max_length: int) -> str:
    """
    Format a ClaudeResult into a Slack-compatible mrkdwn message.

    Args:
        result (ClaudeResult): The result from Claude Code.
        max_length (int): Maximum message length before truncation.

    Returns:
        str: Formatted Slack mrkdwn message.
    """

    output: str = result.output[:max_length]

    if result.is_error:
        return f"⚠️ Claude encountered an error:\n```{output}```"

    if len(result.output) > max_length:
        output += "\n… (truncated)"

    converter: SlackMarkdownConverter = SlackMarkdownConverter()
    converted: str = converter.convert(output)

    return converted


async def _react(
    app: AsyncApp,
    channel: str,
    timestamp: str,
    emoji: str,
) -> None:
    """
    Add an emoji reaction to a Slack message.

    Args:
        app (AsyncApp): The async Slack Bolt app instance.
        channel (str): The Slack channel ID.
        timestamp (str): The message timestamp to react to.
        emoji (str): The emoji name without colons.
    """

    try:
        await app.client.reactions_add(
            channel=channel,
            name=emoji,
            timestamp=timestamp,
        )
    except Exception:
        logger.exception("Failed to add reaction to message in %s", channel)


async def _post(
    app: AsyncApp,
    channel: str,
    thread_ts: str,
    text: str,
) -> None:
    """
    Post a message to a Slack channel in a specific thread.

    Args:
        app (AsyncApp): The async Slack Bolt app instance.
        channel (str): The Slack channel ID.
        thread_ts (str): The thread timestamp to reply in.
        text (str): The message text.
    """

    try:
        await app.client.chat_postMessage(
            channel=channel,
            text=text,
            thread_ts=thread_ts,
        )
    except Exception:
        logger.exception("Failed to post message to Slack channel %s", channel)
