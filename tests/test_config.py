import os
from unittest.mock import patch

import pytest

from claude_slack_bot.config import Config

TEST_PROJECT_PATH = "/tmp/project"


@pytest.fixture
def env_vars():
    return {
        "SLACK_BOT_TOKEN": "xoxb-test-token",
        "SLACK_APP_TOKEN": "xapp-test-token",
        "SLACK_ADMIN_USER": "U001,U002",
    }


class TestFromEnv:
    def test_from_env_valid_config(self, env_vars):
        with patch.dict(os.environ, env_vars, clear=False):
            config = Config.from_env(TEST_PROJECT_PATH)

        assert config.slack_bot_token == "xoxb-test-token"
        assert config.slack_app_token == "xapp-test-token"
        assert config.allowed_user_ids == frozenset({"U001", "U002"})
        assert config.project_path == TEST_PROJECT_PATH
        assert config.claude_timeout_seconds == 300

    def test_from_env_custom_timeout(self, env_vars):
        env_vars["CLAUDE_TIMEOUT_SECONDS"] = "60"

        with patch.dict(os.environ, env_vars, clear=False):
            config = Config.from_env(TEST_PROJECT_PATH)

        assert config.claude_timeout_seconds == 60

    def test_from_env_missing_bot_token_raises(self, env_vars):
        del env_vars["SLACK_BOT_TOKEN"]

        with patch.dict(os.environ, env_vars, clear=True):
            with pytest.raises(OSError, match="SLACK_BOT_TOKEN"):
                Config.from_env(TEST_PROJECT_PATH)

    def test_from_env_missing_app_token_raises(self, env_vars):
        del env_vars["SLACK_APP_TOKEN"]

        with patch.dict(os.environ, env_vars, clear=True):
            with pytest.raises(OSError, match="SLACK_APP_TOKEN"):
                Config.from_env(TEST_PROJECT_PATH)

    def test_from_env_empty_user_ids_raises(self, env_vars):
        env_vars["SLACK_ADMIN_USER"] = "  ,  , "

        with patch.dict(os.environ, env_vars, clear=False):
            with pytest.raises(ValueError, match="at least one user ID"):
                Config.from_env(TEST_PROJECT_PATH)

    def test_from_env_expands_tilde_in_project_path(self, env_vars):
        with patch.dict(os.environ, env_vars, clear=False):
            config = Config.from_env("~/my-project")

        assert "~" not in config.project_path
        assert config.project_path.endswith("/my-project")

    def test_from_env_strips_whitespace_from_user_ids(self, env_vars):
        env_vars["SLACK_ADMIN_USER"] = " U001 , U002 "

        with patch.dict(os.environ, env_vars, clear=False):
            config = Config.from_env(TEST_PROJECT_PATH)

        assert config.allowed_user_ids == frozenset({"U001", "U002"})
