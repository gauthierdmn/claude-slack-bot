import logging
from dataclasses import dataclass
from typing import Any

from claude_agent_sdk import (
    ClaudeAgentOptions,
    Message,
    ResultMessage,
    SystemMessage,
    query,
)
from claude_agent_sdk._errors import MessageParseError
from claude_agent_sdk._internal import client as _sdk_client
from claude_agent_sdk._internal import message_parser as _sdk_parser

SESSION_ID_INIT_SUBTYPE: str = "init"

logger: logging.Logger = logging.getLogger(__name__)

_original_parse_message = _sdk_parser.parse_message


def _patched_parse_message(data: dict[str, Any]) -> Message:
    """
    Wrap the SDK's ``parse_message`` to gracefully handle unknown message types.

    The upstream implementation raises ``MessageParseError`` for types it does
    not recognise (e.g. ``rate_limit_event``).  Because ``parse_message`` is
    called *inside* the ``process_query`` async generator, the exception kills
    the generator and the underlying subprocess transport.  This wrapper
    catches the error and returns a ``SystemMessage`` placeholder so the
    stream stays alive.

    Args:
        data (dict[str, Any]): Raw message dict from the CLI stream.

    Returns:
        Message: The parsed message, or a SystemMessage placeholder for
            unknown types.
    """

    try:
        return _original_parse_message(data)
    except MessageParseError:
        is_dict: bool = isinstance(data, dict)
        message_type: str = data.get("type", "unknown") if is_dict else "unknown"

        logger.debug("SDK ignoring unknown message type: %s", message_type)

        return SystemMessage(
            subtype=message_type,
            data=data if is_dict else {},
        )


_sdk_parser.parse_message = _patched_parse_message
_sdk_client.parse_message = _patched_parse_message  # type: ignore[attr-defined]


@dataclass(frozen=True)
class ClaudeResult:
    """
    Result from a Claude Code invocation.

    Attributes:
        output (str): The text output from Claude.
        is_error (bool): Whether the invocation ended in error.
        num_turns (int): Number of agentic turns taken.
        duration_ms (int): Wall-clock duration in milliseconds.
        session_id (str): The Claude session ID for resumption.
    """

    output: str
    is_error: bool
    num_turns: int
    duration_ms: int
    session_id: str


async def run_claude(
    prompt: str,
    project_path: str,
    model: str = "",
    max_turns: int = 0,
    cli_path: str = "",
    session_id: str = "",
) -> ClaudeResult:
    """
    Run Claude Code via the Agent SDK and return the result.

    Args:
        prompt (str): The user's prompt to pass to Claude.
        project_path (str): Working directory for Claude Code.
        model (str): Optional model override (empty string to skip).
        max_turns (int): Maximum agentic turns (0 for unlimited).
        cli_path (str): Path to the Claude CLI binary (empty to use bundled).
        session_id (str): Optional session ID to resume a previous conversation.

    Returns:
        ClaudeResult: The parsed result from Claude Code.
    """

    options: ClaudeAgentOptions = ClaudeAgentOptions(
        permission_mode="bypassPermissions",
        cwd=project_path,
        model=model or None,
        max_turns=max_turns if max_turns > 0 else None,
        cli_path=cli_path or None,
        resume=session_id or None,
    )

    result: ClaudeResult | None = None
    captured_session_id: str = ""

    async for message in query(prompt=prompt, options=options):
        if (
            isinstance(message, SystemMessage)
            and message.subtype == SESSION_ID_INIT_SUBTYPE
        ):
            captured_session_id = message.data.get("session_id", "")

        if isinstance(message, ResultMessage):
            output: str = message.result or "Done, no output."
            captured_session_id = message.session_id or captured_session_id

            result = ClaudeResult(
                output=output,
                is_error=message.is_error,
                num_turns=message.num_turns,
                duration_ms=message.duration_ms,
                session_id=captured_session_id,
            )

    if result is not None:
        return result

    return ClaudeResult(
        output="No result received from Claude.",
        is_error=True,
        num_turns=0,
        duration_ms=0,
        session_id=captured_session_id,
    )
