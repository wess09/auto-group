from app.core.config import Settings


def test_cors_origins_are_split() -> None:
    settings = Settings(cors_origins="https://a.example, https://b.example")

    assert settings.cors_origin_list == ["https://a.example", "https://b.example"]


def test_cors_origins_default_to_wildcard() -> None:
    settings = Settings(cors_origins="")

    assert settings.cors_origin_list == ["*"]
