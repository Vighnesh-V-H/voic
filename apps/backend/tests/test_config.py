from app.core.config import Settings


def test_standard_postgresql_url_uses_psycopg3_driver():
    settings = Settings(database_url="postgresql://user:password@localhost/voic")

    assert settings.database_url == "postgresql+psycopg://user:password@localhost/voic"
