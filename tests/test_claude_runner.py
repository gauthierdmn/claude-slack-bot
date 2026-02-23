# type: ignore
from unittest.mock import MagicMock, patch

import pytest
from claude_agent_sdk import ClaudeAgentOptions, SystemMessage
from claude_agent_sdk._errors import MessageParseError

from claude_slack_bot.claude_runner import (
    _original_parse_message,
    _patched_parse_message,
    run_claude,
)


async def _async_gen(*items):
    for item in items:
        yield item


class TestPatchedParseMessage:
    def test_delegates_to_original_for_known_types(self):
        data = {
            "type": "result",
            "subtype": "success",
            "result": "hello",
            "is_error": False,
            "num_turns": 1,
            "duration_ms": 100,
            "duration_api_ms": 50,
            "session_id": "abc",
        }

        message = _patched_parse_message(data)

        assert type(message).__name__ == "ResultMessage"

    def test_returns_system_message_for_unknown_types(self):
        data = {"type": "rate_limit_event", "retry_after_ms": 5000}

        message = _patched_parse_message(data)

        assert isinstance(message, SystemMessage)
        assert message.subtype == "rate_limit_event"
        assert message.data == data

    def test_handles_missing_type_field(self):
        data = {"foo": "bar"}

        message = _patched_parse_message(data)

        assert isinstance(message, SystemMessage)

    def test_original_still_raises_for_unknown_types(self):
        data = {"type": "rate_limit_event"}

        with pytest.raises(MessageParseError):
            _original_parse_message(data)


class TestRunClaude:
    @pytest.mark.asyncio
    async def test_success_returns_result(self):
        result_msg = MagicMock()
        result_msg.result = "All done!"
        result_msg.is_error = False
        result_msg.num_turns = 3
        result_msg.duration_ms = 5000
        result_msg.session_id = "sess-123"

        with (
            patch(
                "claude_slack_bot.claude_runner.query",
                return_value=_async_gen(result_msg),
            ),
            patch(
                "claude_slack_bot.claude_runner.ResultMessage",
                new=type(result_msg),
            ),
        ):
            result = await run_claude("hello", "/tmp/project")

        assert result.output == "All done!"
        assert result.is_error is False
        assert result.num_turns == 3
        assert result.duration_ms == 5000
        assert result.session_id == "sess-123"

    @pytest.mark.asyncio
    async def test_error_result(self):
        result_msg = MagicMock()
        result_msg.result = "Something broke"
        result_msg.is_error = True
        result_msg.num_turns = 1
        result_msg.duration_ms = 200
        result_msg.session_id = "sess-456"

        with (
            patch(
                "claude_slack_bot.claude_runner.query",
                return_value=_async_gen(result_msg),
            ),
            patch(
                "claude_slack_bot.claude_runner.ResultMessage",
                new=type(result_msg),
            ),
        ):
            result = await run_claude("hello", "/tmp/project")

        assert result.is_error is True
        assert result.output == "Something broke"

    @pytest.mark.asyncio
    async def test_no_result_message_returns_fallback(self):
        assistant_msg = MagicMock()

        with patch(
            "claude_slack_bot.claude_runner.query",
            return_value=_async_gen(assistant_msg),
        ):
            result = await run_claude("hello", "/tmp/project")

        assert result.is_error is True
        assert result.output == "No result received from Claude."

    @pytest.mark.asyncio
    async def test_empty_result_defaults_to_done(self):
        result_msg = MagicMock()
        result_msg.result = ""
        result_msg.is_error = False
        result_msg.num_turns = 1
        result_msg.duration_ms = 100
        result_msg.session_id = ""

        with (
            patch(
                "claude_slack_bot.claude_runner.query",
                return_value=_async_gen(result_msg),
            ),
            patch(
                "claude_slack_bot.claude_runner.ResultMessage",
                new=type(result_msg),
            ),
        ):
            result = await run_claude("hello", "/tmp/project")

        assert result.output == "Done, no output."

    @pytest.mark.asyncio
    async def test_model_and_max_turns_passed_to_options(self):
        result_msg = MagicMock()
        result_msg.result = "ok"
        result_msg.is_error = False
        result_msg.num_turns = 1
        result_msg.duration_ms = 100
        result_msg.session_id = ""

        with (
            patch(
                "claude_slack_bot.claude_runner.query",
                return_value=_async_gen(result_msg),
            ),
            patch(
                "claude_slack_bot.claude_runner.ResultMessage",
                new=type(result_msg),
            ),
            patch(
                "claude_slack_bot.claude_runner.ClaudeAgentOptions",
                wraps=ClaudeAgentOptions,
            ) as mock_options_cls,
        ):
            await run_claude(
                "hello",
                "/tmp/project",
                model="claude-sonnet-4-6",
                max_turns=10,
            )

        call_kwargs = mock_options_cls.call_args[1]
        assert call_kwargs["model"] == "claude-sonnet-4-6"
        assert call_kwargs["max_turns"] == 10
        assert call_kwargs["cwd"] == "/tmp/project"

    @pytest.mark.asyncio
    async def test_no_model_omits_key(self):
        result_msg = MagicMock()
        result_msg.result = "ok"
        result_msg.is_error = False
        result_msg.num_turns = 1
        result_msg.duration_ms = 100
        result_msg.session_id = ""

        with (
            patch(
                "claude_slack_bot.claude_runner.query",
                return_value=_async_gen(result_msg),
            ),
            patch(
                "claude_slack_bot.claude_runner.ResultMessage",
                new=type(result_msg),
            ),
            patch(
                "claude_slack_bot.claude_runner.ClaudeAgentOptions",
                wraps=ClaudeAgentOptions,
            ) as mock_options_cls,
        ):
            await run_claude("hello", "/tmp/project", model="", max_turns=0)

        call_kwargs = mock_options_cls.call_args[1]
        assert call_kwargs["model"] is None
        assert call_kwargs["max_turns"] is None

    @pytest.mark.asyncio
    async def test_skips_unknown_message_types(self):
        unknown_msg = SystemMessage(subtype="rate_limit_event", data={})
        result_msg = MagicMock()
        result_msg.result = "Success after rate limit"
        result_msg.is_error = False
        result_msg.num_turns = 2
        result_msg.duration_ms = 3000
        result_msg.session_id = "sess-789"

        with (
            patch(
                "claude_slack_bot.claude_runner.query",
                return_value=_async_gen(unknown_msg, result_msg),
            ),
            patch(
                "claude_slack_bot.claude_runner.ResultMessage",
                new=type(result_msg),
            ),
        ):
            result = await run_claude("hello", "/tmp/project")

        assert result.output == "Success after rate limit"
        assert result.is_error is False

    @pytest.mark.asyncio
    async def test_session_id_captured_from_init_message(self):
        init_msg = SystemMessage(
            subtype="init",
            data={"session_id": "sess-from-init"},
        )
        result_msg = MagicMock()
        result_msg.result = "ok"
        result_msg.is_error = False
        result_msg.num_turns = 1
        result_msg.duration_ms = 100
        result_msg.session_id = ""

        with (
            patch(
                "claude_slack_bot.claude_runner.query",
                return_value=_async_gen(init_msg, result_msg),
            ),
            patch(
                "claude_slack_bot.claude_runner.ResultMessage",
                new=type(result_msg),
            ),
        ):
            result = await run_claude("hello", "/tmp/project")

        assert result.session_id == "sess-from-init"

    @pytest.mark.asyncio
    async def test_session_id_from_result_takes_precedence(self):
        init_msg = SystemMessage(
            subtype="init",
            data={"session_id": "sess-from-init"},
        )
        result_msg = MagicMock()
        result_msg.result = "ok"
        result_msg.is_error = False
        result_msg.num_turns = 1
        result_msg.duration_ms = 100
        result_msg.session_id = "sess-from-result"

        with (
            patch(
                "claude_slack_bot.claude_runner.query",
                return_value=_async_gen(init_msg, result_msg),
            ),
            patch(
                "claude_slack_bot.claude_runner.ResultMessage",
                new=type(result_msg),
            ),
        ):
            result = await run_claude("hello", "/tmp/project")

        assert result.session_id == "sess-from-result"

    @pytest.mark.asyncio
    async def test_session_id_passed_as_resume_option(self):
        result_msg = MagicMock()
        result_msg.result = "ok"
        result_msg.is_error = False
        result_msg.num_turns = 1
        result_msg.duration_ms = 100
        result_msg.session_id = "sess-resumed"

        with (
            patch(
                "claude_slack_bot.claude_runner.query",
                return_value=_async_gen(result_msg),
            ),
            patch(
                "claude_slack_bot.claude_runner.ResultMessage",
                new=type(result_msg),
            ),
            patch(
                "claude_slack_bot.claude_runner.ClaudeAgentOptions",
                wraps=ClaudeAgentOptions,
            ) as mock_options_cls,
        ):
            await run_claude("hello", "/tmp/project", session_id="sess-existing")

        call_kwargs = mock_options_cls.call_args[1]
        assert call_kwargs["resume"] == "sess-existing"

    @pytest.mark.asyncio
    async def test_no_session_id_sets_resume_to_none(self):
        result_msg = MagicMock()
        result_msg.result = "ok"
        result_msg.is_error = False
        result_msg.num_turns = 1
        result_msg.duration_ms = 100
        result_msg.session_id = ""

        with (
            patch(
                "claude_slack_bot.claude_runner.query",
                return_value=_async_gen(result_msg),
            ),
            patch(
                "claude_slack_bot.claude_runner.ResultMessage",
                new=type(result_msg),
            ),
            patch(
                "claude_slack_bot.claude_runner.ClaudeAgentOptions",
                wraps=ClaudeAgentOptions,
            ) as mock_options_cls,
        ):
            await run_claude("hello", "/tmp/project", session_id="")

        call_kwargs = mock_options_cls.call_args[1]
        assert call_kwargs["resume"] is None
