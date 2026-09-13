import json
import threading

import httpx
import pytest

from minecraft_ia.assistant import Reply
from minecraft_ia.db import HistoryEntry
from minecraft_ia.server import make_server

TOKEN = "t" * 40
PLAYER = "0f1e2d3c-0000-0000-0000-000000000001"


class FakeAssistant:
    def __init__(self):
        self.asked = []

    def ask(self, player, name, question):
        self.asked.append((player, name, question))
        return Reply(7, "Réponse", ["kb:mods/aether.md"], "ok")

    def vote(self, answer_id, player, up):
        return None if up else Reply(8, "Relance", [], "unknown")

    def history(self, player, limit):
        return [HistoryEntry(7, "q", "r", [], "ok", None, "2026-09-12T12:00:00+00:00")]


@pytest.fixture
def server():
    assistant = FakeAssistant()
    srv = make_server(assistant, TOKEN, "127.0.0.1", 0)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    with httpx.Client(base_url=base, headers={"Authorization": f"Bearer {TOKEN}"}) as client:
        yield client, assistant
    srv.shutdown()
    srv.server_close()


def test_health_without_auth(server):
    client, _ = server
    assert httpx.get(client.base_url.join("/health")).json() == {"ok": True}


def test_ask(server):
    client, assistant = server
    r = client.post("/ask", json={"player": PLAYER, "name": "Steve", "question": "portail ?"})
    assert r.status_code == 200
    assert r.json() == {"id": 7, "text": "Réponse", "sources": ["kb:mods/aether.md"], "status": "ok"}
    assert assistant.asked == [(PLAYER, "Steve", "portail ?")]


def test_vote_and_history(server):
    client, _ = server
    assert client.post("/vote", json={"player": PLAYER, "id": 7, "up": True}).json() == {"ok": True, "retry": None}
    retry = client.post("/vote", json={"player": PLAYER, "id": 7, "up": False}).json()["retry"]
    assert retry["id"] == 8
    items = client.post("/history", json={"player": PLAYER, "limit": 5}).json()["items"]
    assert items[0]["id"] == 7 and items[0]["vote"] is None


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer faux"}])
def test_auth_required(server, headers):
    client, assistant = server
    r = httpx.post(client.base_url.join("/ask"), headers=headers, json={"player": PLAYER, "name": "S", "question": "q"})
    assert r.status_code == 401 and not assistant.asked


@pytest.mark.parametrize(
    "body",
    [
        {"player": "pas-un-uuid", "name": "Steve", "question": "q"},
        {"player": PLAYER, "name": "Steve; rm", "question": "q"},
        {"player": PLAYER, "name": "Steve", "question": 42},
        {"player": PLAYER, "name": "Steve"},
    ],
)
def test_invalid_payloads(server, body):
    client, assistant = server
    assert client.post("/ask", json=body).status_code == 400 and not assistant.asked


def test_body_too_large_and_bad_json(server):
    client, _ = server
    assert client.post("/ask", content=b"x" * 20000).status_code == 413
    assert client.post("/ask", content=b"{pas du json").status_code == 400
    assert client.post("/nope", content=json.dumps({})).status_code == 404


def test_refuses_non_loopback_bind():
    with pytest.raises(ValueError):
        make_server(FakeAssistant(), TOKEN, "0.0.0.0", 0)
