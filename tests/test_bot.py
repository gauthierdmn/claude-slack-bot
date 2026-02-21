from unittest.mock import MagicMock, patch

import pytest
from slack_bolt import App

from claude_slack_bot.bot import register_handlers
from claude_slack_bot.config import Config


@pytest.fixture
def config():
    return Config(
        slack_bot_token="xoxb-test",
        slack_app_token="xapp-test",
        allowed_user_ids=frozenset({"U001"}),
        project_path="/tmp/project",
        claude_timeout_seconds=10,
    )


@pytest.fixture
def app(config):
    slack_app = App(
        token="xoxb-test",
        token_verification_enabled=False,
        signing_secret="test-secret",
    )
    register_handlers(slack_app, config)

    return slack_app


@pytest.fixture
def mention_event():
    return {
        "user": "U001",
        "channel": "C001",
        "text": "<@BOT123> fix the bug",
        "ts": "1234567890.123456",
    }


def _invoke_handler(app, event, say):
    for registered_listener in app._listeners:
        if hasattr(registered_listener, "ack_function"):
            registered_listener.ack_function(event=event, say=say)


class TestHandleMention:
    @patch("claude_slack_bot.bot.threading.Thread")
    def test_handle_mention_authorized_user_spawns_worker(
        self,
        mock_thread_cls,
        app,
        mention_event,
    ):
        say = MagicMock()

        _invoke_handler(app, mention_event, say)

        say.assert_called_once()
        mock_thread_cls.assert_called_once()
        mock_thread_cls.return_value.start.assert_called_once()

    def test_handle_mention_unauthorized_user_rejected(self, app):
        say = MagicMock()
        event = {
            "user": "U999",
            "channel": "C001",
            "text": "<@BOT123> hack the planet",
            "ts": "1234567890.123456",
        }

        _invoke_handler(app, event, say)

        say.assert_called_once_with(
            "Sorry, you're not authorized to use this bot.",
            thread_ts="1234567890.123456",
        )

    def test_handle_mention_empty_prompt_rejected(self, app):
        say = MagicMock()
        event = {
            "user": "U001",
            "channel": "C001",
            "text": "<@BOT123>",
            "ts": "1234567890.123456",
        }

        _invoke_handler(app, event, say)

        say.assert_called_once_with(
            "Please provide a prompt after mentioning me.",
            thread_ts="1234567890.123456",
        )

    def test_handle_mention_in_thread_preserves_thread_ts(self, app):
        say = MagicMock()
        event = {
            "user": "U001",
            "channel": "C001",
            "text": "<@BOT123> help",
            "ts": "1234567890.999999",
            "thread_ts": "1234567890.000001",
        }

        with patch("claude_slack_bot.bot.threading.Thread"):
            _invoke_handler(app, event, say)

        say.assert_called_once_with(
            "On it! Running: `help`",
            thread_ts="1234567890.000001",
        )
