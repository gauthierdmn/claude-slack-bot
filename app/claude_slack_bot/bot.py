import logging
import subprocess
import threading
from typing import Any

from slack_bolt import App

from claude_slack_bot.config import Config

logger: logging.Logger = logging.getLogger(__name__)


def register_handlers(app: App, config: Config) -> None:
    """
    Register event handlers on the Slack Bolt application.

    Args:
        app (App): A Slack Bolt app instance.
        config (Config): Application configuration.
    """

    @app.event("app_mention")
    def handle_mention(event: dict[str, Any], say: Any) -> None:
        """
        Handle an app_mention event from Slack.

        Args:
            event (dict[str, Any]): The Slack event payload.
            say (Any): Slack's say utility for posting messages.
        """

        user_id: str = event.get("user", "")
        channel: str = event.get("channel", "")
        text: str = event.get("text", "")
        # Reply in the existing thread, or start a new thread on the message
        thread_ts: str = event.get("thread_ts", event.get("ts", ""))

        if user_id not in config.allowed_user_ids:
            logger.warning("Unauthorized mention from user %s", user_id)
            say("Sorry, you're not authorized to use this bot.", thread_ts=thread_ts)

            return

        # Strip the @mention prefix (format: <@BOTID> prompt)
        prompt: str = text.split(">", 1)[-1].strip()

        if not prompt:
            say("Please provide a prompt after mentioning me.", thread_ts=thread_ts)

            return

        logger.info("Received prompt from %s: %s", user_id, prompt)
        say(f"On it! Running: `{prompt}`", thread_ts=thread_ts)

        threading.Thread(
            target=_run_claude,
            args=(app, config, prompt, channel, thread_ts),
            daemon=True,
        ).start()

    return


def _run_claude(
    app: App,
    config: Config,
    prompt: str,
    channel: str,
    thread_ts: str,
) -> None:
    """
    Run Claude Code as a subprocess and post the result back to Slack.

    Args:
        app (App): The Slack Bolt app instance for posting messages.
        config (Config): Application configuration.
        prompt (str): The user's prompt to pass to Claude Code.
        channel (str): The Slack channel ID to post results in.
        thread_ts (str): The thread timestamp to reply in.
    """

    logger.info("Starting Claude Code with prompt: %s", prompt)

    try:
        result: subprocess.CompletedProcess[str] = subprocess.run(
            ["claude", "--print", prompt],
            capture_output=True,
            text=True,
            timeout=config.claude_timeout_seconds,
            cwd=config.project_path,
        )

        if result.returncode != 0:
            logger.error(
                "Claude exited with code %d: %s",
                result.returncode,
                result.stderr,
            )
            error_output = result.stderr[: config.max_slack_message_length]
            _post(
                app,
                channel,
                thread_ts,
                f"⚠️ Claude exited with error:\n```{error_output}```",
            )

            return

        output: str = result.stdout.strip() or "Done, no output."
        truncated: str = output[: config.max_slack_message_length]

        if len(output) > config.max_slack_message_length:
            truncated += "\n… (truncated)"

        logger.info("Claude finished successfully")
        _post(app, channel, thread_ts, f"✅ Finished:\n```{truncated}```")

    except subprocess.TimeoutExpired:
        logger.error("Claude timed out after %d seconds", config.claude_timeout_seconds)
        _post(
            app,
            channel,
            thread_ts,
            f"⏱️ Timed out after {config.claude_timeout_seconds} seconds.",
        )
    except FileNotFoundError:
        logger.error("'claude' command not found — is Claude Code installed?")
        _post(
            app,
            channel,
            thread_ts,
            "❌ `claude` command not found. Is Claude Code installed and on PATH?",
        )
    except Exception:
        logger.exception("Unexpected error running Claude")
        _post(
            app,
            channel,
            thread_ts,
            "❌ An unexpected error occurred. Check the bot logs.",
        )


def _post(app: App, channel: str, thread_ts: str, text: str) -> None:
    """
    Post a message to a Slack channel in a specific thread.

    Args:
        app (App): The Slack Bolt app instance.
        channel (str): The Slack channel ID.
        thread_ts (str): The thread timestamp to reply in.
        text (str): The message text.
    """

    try:
        app.client.chat_postMessage(channel=channel, text=text, thread_ts=thread_ts)
    except Exception:
        logger.exception("Failed to post message to Slack channel %s", channel)
