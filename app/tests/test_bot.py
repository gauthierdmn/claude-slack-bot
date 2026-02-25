# type: ignore
from unittest.mock import AsyncMock, patch

import pytest
from slack_bolt.async_app import AsyncApp

from claude_slack_bot.bot import _format_response, register_handlers
from claude_slack_bot.claude_runner import ClaudeResult
from claude_slack_bot.config import Config
from claude_slack_bot.session import SessionQueue, SessionStore


@pytest.fixture
def config():
    return Config(
        slack_bot_token="xoxb-test",
        slack_app_token="xapp-test",
        allowed_user_ids=frozenset({"U001"}),
        project_path="/tmp/project",
    )


@pytest.fixture
def session_store():
    return SessionStore()


@pytest.fixture
def session_queue():
    return SessionQueue()


@pytest.fixture
def app(config, session_store, session_queue):
    slack_app = AsyncApp(
        token="xoxb-test",
        url_verification_enabled=False,
        signing_secret="test-secret",
    )
    register_handlers(slack_app, config, session_store, session_queue)

    return slack_app


@pytest.fixture
def mention_event():
    return {
        "user": "U001",
        "channel": "C001",
        "text": "<@BOT123> fix the bug",
        "ts": "1234567890.123456",
    }


@pytest.fixture
def dm_event():
    return {
        "user": "U001",
        "channel": "D001",
        "channel_type": "im",
        "text": "fix the bug",
        "ts": "1234567890.123456",
    }


async def _invoke_handler(app, event, say, handler_name=None):
    for registered_listener in app._async_listeners:
        if not hasattr(registered_listener, "ack_function"):
            continue

        if handler_name is not None:
            func_name = getattr(registered_listener.ack_function, "__name__", "")

            if func_name != handler_name:
                continue

        await registered_listener.ack_function(event=event, say=say)


class TestHandleMention:
    @pytest.mark.asyncio
    @patch("claude_slack_bot.bot._react", new_callable=AsyncMock)
    @patch("claude_slack_bot.bot.SessionQueue.enqueue", new_callable=AsyncMock)
    async def test_handle_mention_authorized_user_enqueues_job(
        self,
        mock_enqueue,
        mock_react,
        app,
        mention_event,
    ):
        say = AsyncMock()

        await _invoke_handler(app, mention_event, say)

        say.assert_not_called()
        mock_react.assert_called_once_with(app, "C001", "1234567890.123456", "eyes")
        mock_enqueue.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_mention_unauthorized_user_rejected(self, app):
        say = AsyncMock()
        event = {
            "user": "U999",
            "channel": "C001",
            "text": "<@BOT123> hack the planet",
            "ts": "1234567890.123456",
        }

        await _invoke_handler(app, event, say)

        say.assert_called_once_with(
            "Sorry, you're not authorized to use this bot.",
            thread_ts="1234567890.123456",
        )

    @pytest.mark.asyncio
    async def test_handle_mention_empty_prompt_rejected(self, app):
        say = AsyncMock()
        event = {
            "user": "U001",
            "channel": "C001",
            "text": "<@BOT123>",
            "ts": "1234567890.123456",
        }

        await _invoke_handler(app, event, say)

        say.assert_called_once_with(
            "Please provide a prompt after mentioning me.",
            thread_ts="1234567890.123456",
        )

    @pytest.mark.asyncio
    @patch("claude_slack_bot.bot._react", new_callable=AsyncMock)
    @patch("claude_slack_bot.bot.SessionQueue.enqueue", new_callable=AsyncMock)
    async def test_handle_mention_in_thread_reacts_with_eyes(
        self,
        mock_enqueue,
        mock_react,
        app,
    ):
        say = AsyncMock()
        event = {
            "user": "U001",
            "channel": "C001",
            "text": "<@BOT123> help",
            "ts": "1234567890.999999",
            "thread_ts": "1234567890.000001",
        }

        await _invoke_handler(app, event, say)

        say.assert_not_called()
        mock_react.assert_called_once_with(app, "C001", "1234567890.999999", "eyes")


DM_HANDLER: str = "handle_direct_message"


class TestHandleDirectMessage:
    @pytest.mark.asyncio
    @patch("claude_slack_bot.bot._react", new_callable=AsyncMock)
    @patch("claude_slack_bot.bot.SessionQueue.enqueue", new_callable=AsyncMock)
    async def test_dm_enqueues_job(
        self,
        mock_enqueue,
        mock_react,
        app,
        dm_event,
    ):
        say = AsyncMock()

        await _invoke_handler(app, dm_event, say, handler_name=DM_HANDLER)

        say.assert_not_called()
        mock_react.assert_called_once_with(app, "D001", "1234567890.123456", "eyes")
        mock_enqueue.assert_called_once()

    @pytest.mark.asyncio
    async def test_dm_unauthorized_user_rejected(self, app):
        say = AsyncMock()
        event = {
            "user": "U999",
            "channel": "D001",
            "channel_type": "im",
            "text": "hack the planet",
            "ts": "1234567890.123456",
        }

        await _invoke_handler(app, event, say, handler_name=DM_HANDLER)

        say.assert_called_once_with(
            "Sorry, you're not authorized to use this bot.",
            thread_ts="1234567890.123456",
        )

    @pytest.mark.asyncio
    async def test_dm_empty_prompt_rejected(self, app):
        say = AsyncMock()
        event = {
            "user": "U001",
            "channel": "D001",
            "channel_type": "im",
            "text": "",
            "ts": "1234567890.123456",
        }

        await _invoke_handler(app, event, say, handler_name=DM_HANDLER)

        say.assert_called_once_with(
            "Please provide a prompt after mentioning me.",
            thread_ts="1234567890.123456",
        )

    @pytest.mark.asyncio
    async def test_dm_ignores_non_im_channel_type(self, app):
        say = AsyncMock()
        event = {
            "user": "U001",
            "channel": "C001",
            "channel_type": "channel",
            "text": "hello",
            "ts": "1234567890.123456",
        }

        await _invoke_handler(app, event, say, handler_name=DM_HANDLER)

        say.assert_not_called()

    @pytest.mark.asyncio
    async def test_dm_ignores_subtyped_messages(self, app):
        say = AsyncMock()
        event = {
            "user": "U001",
            "channel": "D001",
            "channel_type": "im",
            "subtype": "message_changed",
            "text": "edited text",
            "ts": "1234567890.123456",
        }

        await _invoke_handler(app, event, say, handler_name=DM_HANDLER)

        say.assert_not_called()

    @pytest.mark.asyncio
    @patch("claude_slack_bot.bot._react", new_callable=AsyncMock)
    @patch("claude_slack_bot.bot.SessionQueue.enqueue", new_callable=AsyncMock)
    async def test_dm_in_thread_reacts_with_eyes(
        self,
        mock_enqueue,
        mock_react,
        app,
    ):
        say = AsyncMock()
        event = {
            "user": "U001",
            "channel": "D001",
            "channel_type": "im",
            "text": "follow up",
            "ts": "1234567890.999999",
            "thread_ts": "1234567890.000001",
        }

        await _invoke_handler(app, event, say, handler_name=DM_HANDLER)

        say.assert_not_called()
        mock_react.assert_called_once_with(app, "D001", "1234567890.999999", "eyes")


class TestFormatResponse:
    def test_format_response_returns_plain_output(self):
        result = ClaudeResult(
            output="All done!",
            is_error=False,
            num_turns=3,
            duration_ms=12500,
            session_id="sess-abc",
        )

        message = _format_response(result, max_length=2900)

        assert "All done!" in message
        assert "Finished" not in message
        assert "Turns" not in message
        assert "Duration" not in message

    def test_format_response_converts_markdown_bold(self):
        result = ClaudeResult(
            output="This is **bold** text",
            is_error=False,
            num_turns=1,
            duration_ms=100,
            session_id="sess-abc",
        )

        message = _format_response(result, max_length=2900)

        assert "**bold**" not in message
        assert "*bold*" in message

    def test_format_response_converts_markdown_links(self):
        result = ClaudeResult(
            output="See [docs](https://example.com)",
            is_error=False,
            num_turns=1,
            duration_ms=100,
            session_id="sess-abc",
        )

        message = _format_response(result, max_length=2900)

        assert "[docs](https://example.com)" not in message
        assert "<https://example.com|docs>" in message

    def test_format_response_error(self):
        result = ClaudeResult(
            output="Something broke",
            is_error=True,
            num_turns=1,
            duration_ms=500,
            session_id="sess-abc",
        )

        message = _format_response(result, max_length=2900)

        assert "⚠️" in message
        assert "Something broke" in message

    def test_format_response_truncates_long_output(self):
        result = ClaudeResult(
            output="x" * 5000,
            is_error=False,
            num_turns=5,
            duration_ms=10000,
            session_id="sess-abc",
        )

        message = _format_response(result, max_length=100)

        assert "… (truncated)" in message
