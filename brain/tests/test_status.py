import json
import socket
import socketserver
import struct
import threading

import pytest

from minecraft_ia.status import live_status, read_varint, server_status, varint


def test_varint_roundtrip():
    for value in (0, 1, 127, 128, 255, 25565, 2**31 - 1, -1):
        assert read_varint(iter(varint(value)).__next__) == value


class _Ping(socketserver.BaseRequestHandler):
    response: dict

    def handle(self):
        f = self.request.makefile("rb")

        def byte():
            return f.read(1)[0]

        for _ in range(2):  # handshake puis status request
            length = read_varint(byte)
            f.read(length)
        body = json.dumps(self.response).encode()
        packet = varint(0) + varint(len(body)) + body
        self.request.sendall(varint(len(packet)) + packet)


@pytest.fixture
def ping_server():
    servers = []

    def start(response):
        handler = type("Handler", (_Ping,), {"response": response})
        server = socketserver.TCPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        servers.append(server)
        return server.server_address[1]

    yield start
    for server in servers:
        server.shutdown()
        server.server_close()


def test_online_server(ping_server):
    port = ping_server(
        {
            "version": {"name": "1.21.1", "protocol": 767},
            "players": {"max": 5, "online": 2, "sample": [{"name": "Steve", "id": "x"}, {"name": "Alex", "id": "y"}]},
            "description": {"text": "§aServeur des potes"},
        }
    )
    assert server_status("127.0.0.1", port) == {
        "online": True,
        "version": "1.21.1",
        "motd": "Serveur des potes",
        "players_online": 2,
        "players_max": 5,
        "players": ["Steve", "Alex"],
    }


def test_empty_server_has_no_sample(ping_server):
    port = ping_server({"version": {"name": "1.21.1"}, "players": {"max": 5, "online": 0}, "description": "MOTD"})
    status = server_status("127.0.0.1", port)
    assert status["players"] == [] and status["motd"] == "MOTD"


def test_offline_server():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    assert server_status("127.0.0.1", port, timeout=0.5) == {"online": False}


def test_garbage_response_is_offline():
    class Garbage(socketserver.BaseRequestHandler):
        def handle(self):
            self.request.sendall(struct.pack(">B", 5) + b"\x00\x03abc")

    server = socketserver.TCPServer(("127.0.0.1", 0), Garbage)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        assert server_status("127.0.0.1", server.server_address[1], timeout=0.5) == {"online": False}
    finally:
        server.shutdown()
        server.server_close()


LIVE = {
    "updated": 1000,
    "tps": 19.8,
    "mspt": 12.3,
    "players": [{"name": "Steve", "dimension": "minecraft:overworld", "x": 1, "y": 64, "z": -3}],
}


def test_live_status_merges_fresh_snapshot(tmp_path):
    live = tmp_path / "live.json"
    live.write_text(json.dumps(LIVE), encoding="utf-8")
    status = live_status(lambda: {"online": True, "players": ["Steve"]}, live, now=lambda: 1010)
    assert status["tps"] == 19.8 and status["mspt"] == 12.3
    assert status["positions"] == LIVE["players"]


@pytest.mark.parametrize("content", [None, "{pas du json", json.dumps({**LIVE, "updated": 900})])
def test_live_status_ignores_missing_broken_or_stale_snapshot(tmp_path, content):
    live = tmp_path / "live.json"
    if content is not None:
        live.write_text(content, encoding="utf-8")
    status = live_status(lambda: {"online": True}, live, now=lambda: 1010)
    assert status == {"online": True, "live": "indisponible (TPS et positions envoyés par le mod serveur)"}


def test_live_status_offline_skips_snapshot(tmp_path):
    live = tmp_path / "live.json"
    live.write_text(json.dumps(LIVE), encoding="utf-8")
    assert live_status(lambda: {"online": False}, live, now=lambda: 1010) == {"online": False}
