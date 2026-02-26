# type: ignore
import os

import pytest

from claude_slack_bot.claude_runner import ClaudeResult, run_claude


@pytest.mark.integration
class TestIntegration:
    @pytest.mark.asyncio
    async def test_run_claude_returns_result(self):
        os.environ.pop("CLAUDECODE", None)

        result = await run_claude(
            prompt="What is 2+2? Reply with ONLY the number, nothing else.",
            project_path="/tmp",
            max_turns=1,
        )

        assert isinstance(result, ClaudeResult)
        assert result.is_error is False
        assert "4" in result.output
        assert result.num_turns >= 1
        assert result.duration_ms > 0
        assert result.session_id != ""
