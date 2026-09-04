from app.core.config import Settings
from app.services.calls.vobiz import is_configured


def test_standard_postgresql_url_uses_psycopg3_driver():
    settings = Settings(database_url="postgresql://user:password@localhost/voic")

    assert settings.database_url == "postgresql+psycopg://user:password@localhost/voic"


def test_voice_calling_disabled_by_default():
    assert is_configured(Settings()) is False


def test_voice_calling_enabled_only_when_complete():
    full = {
        "vobiz_auth_id": "auth_test_id",
        "vobiz_auth_token": "auth_test_token",
        "vobiz_caller_id": "+911234567890",
        "vobiz_answer_url": "https://voic.example.com/voice/answer",
        "vobiz_public_base_url": "https://voic.example.com",
        "voice_callback_token": "token_test_123",
    }

    assert is_configured(Settings(**full)) is True
    for missing in full:
        partial = {key: value for key, value in full.items() if key != missing}
        assert is_configured(Settings(**partial)) is False
