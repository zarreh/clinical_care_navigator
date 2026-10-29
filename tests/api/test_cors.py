from fastapi.testclient import TestClient

from navigator.api.main import app

client = TestClient(app)


def _preflight(origin: str) -> int:
    response = client.options(
        "/conversations",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    return response.status_code


def test_configured_frontend_origin_is_allowed() -> None:
    assert _preflight("http://localhost:3000") == 200


def test_arbitrary_origin_is_refused() -> None:
    assert _preflight("https://evil.example") == 400


def test_development_accepts_any_localhost_port() -> None:
    # `next dev` moves to :3001 when :3000 is busy; the page must keep working.
    for origin in ("http://localhost:3001", "http://127.0.0.1:3100", "http://localhost"):
        assert _preflight(origin) == 200


def test_development_still_refuses_look_alike_hosts() -> None:
    for origin in (
        "http://localhost.evil.example",
        "http://evil.example:3000",
        "https://localhost@evil.example",
    ):
        assert _preflight(origin) == 400


def test_production_trusts_only_the_configured_origins() -> None:
    from navigator.api.main import cors_options
    from navigator.settings import Settings

    options = cors_options(
        Settings(environment="production", frontend_origins=["https://clinical.example.com"])
    )

    assert options["allow_origins"] == ["https://clinical.example.com"]
    assert "allow_origin_regex" not in options  # localhost is not trusted on a public site
