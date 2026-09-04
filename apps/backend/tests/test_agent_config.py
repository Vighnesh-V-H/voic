from app.core.config import Settings
from app.services.agent.elevenlabs import is_configured


def test_agent_disabled_by_default():
    assert is_configured(Settings(_env_file=None)) is False


def test_agent_enabled_only_when_complete():
    full = {
        "elevenlabs_api_key": "key_test_123",
        "elevenlabs_agent_id": "agent_test_123",
        "elevenlabs_phone_number_id": "number_test_123",
        "agent_tool_token": "tool_test_123",
    }

    assert is_configured(Settings(_env_file=None, **full)) is True
    for missing in full:
        partial = {key: value for key, value in full.items() if key != missing}
        assert is_configured(Settings(_env_file=None, **partial)) is False
