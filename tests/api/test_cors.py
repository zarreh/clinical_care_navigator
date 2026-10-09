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
