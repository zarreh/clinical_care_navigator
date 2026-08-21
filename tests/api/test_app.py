from fastapi.testclient import TestClient

from navigator.api.main import app

client = TestClient(app)


def test_healthz() -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_oversized_body_is_rejected_before_routing() -> None:
    response = client.post("/conversations/stream", json={"question": "x" * 20_000})
    assert response.status_code == 413


def test_stream_emits_every_node_then_end() -> None:
    with client.stream("POST", "/conversations/stream", json={"question": "hello"}) as response:
        assert response.status_code == 200
        nodes = [
            line.removeprefix("data: ")
            for line in response.iter_lines()
            if line.startswith("data: ")
        ]

    assert any('"echo"' in node for node in nodes)
    assert any('"done"' in node for node in nodes)
    assert '"__end__"' in nodes[-1]
