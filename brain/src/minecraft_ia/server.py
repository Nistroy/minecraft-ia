"""API HTTP locale (127.0.0.1) appelée par le mod serveur. Jeton partagé, entrées validées."""

from __future__ import annotations

import hmac
import json
import logging
import re
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Protocol

from .assistant import Reply
from .config import LOOPBACK
from .db import HistoryEntry

log = logging.getLogger(__name__)

MAX_BODY = 16 * 1024
_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_NAME = re.compile(r"^[A-Za-z0-9_]{1,16}$")


class AssistantApi(Protocol):
    def ask(self, player: str, player_name: str, question: str) -> Reply: ...
    def vote(self, answer_id: int, player: str, up: bool) -> Reply | None: ...
    def history(self, player: str, limit: int) -> list[HistoryEntry]: ...


class BadRequest(Exception):
    pass


def _reply_json(reply: Reply | None) -> dict | None:
    if reply is None:
        return None
    return {"id": reply.answer_id, "text": reply.text, "sources": reply.sources, "status": reply.status}


def _history_json(entry: HistoryEntry) -> dict:
    data = asdict(entry)
    return {"id": data.pop("answer_id"), "at": data.pop("asked_at"), **data}


def _player(body: dict) -> str:
    player = body.get("player")
    if not isinstance(player, str) or not _UUID.match(player):
        raise BadRequest("player")
    return player


def _int(body: dict, key: str, default: int | None = None) -> int:
    value = body.get(key, default)
    if not isinstance(value, int) or isinstance(value, bool):
        raise BadRequest(key)
    return value


class _Handler(BaseHTTPRequestHandler):
    assistant: AssistantApi
    token: str
    server_version = "minecraft-ia"

    def do_GET(self) -> None:  # noqa: N802 — nom imposé par http.server
        if self.path == "/health":
            self._send(200, {"ok": True})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        routes = {"/ask": self._ask, "/vote": self._vote, "/history": self._history}
        route = routes.get(self.path)
        if route is None:
            self._send(404, {"error": "not found"})
            return
        if not self._authorized():
            self._send(401, {"error": "unauthorized"})
            return
        length = self.headers.get("Content-Length")
        if length is None or not length.isdigit():
            self._send(400, {"error": "content-length"})
            return
        if int(length) > MAX_BODY:
            self._send(413, {"error": "too large"})
            return
        try:
            body = json.loads(self.rfile.read(int(length)) or b"{}")
            if not isinstance(body, dict):
                raise BadRequest("body")
            self._send(200, route(body))
        except (json.JSONDecodeError, UnicodeDecodeError, BadRequest) as e:
            self._send(400, {"error": f"invalid: {e}"})
        except Exception:
            log.exception("erreur interne sur %s", self.path)
            self._send(500, {"error": "internal"})

    def _authorized(self) -> bool:
        header = self.headers.get("Authorization", "")
        return hmac.compare_digest(header.encode(), f"Bearer {self.token}".encode())

    def _ask(self, body: dict) -> dict:
        name, question = body.get("name"), body.get("question")
        if not isinstance(name, str) or not _NAME.match(name):
            raise BadRequest("name")
        if not isinstance(question, str):
            raise BadRequest("question")
        return _reply_json(self.assistant.ask(_player(body), name, question))

    def _vote(self, body: dict) -> dict:
        up = body.get("up")
        if not isinstance(up, bool):
            raise BadRequest("up")
        retry = self.assistant.vote(_int(body, "id"), _player(body), up)
        return {"ok": True, "retry": _reply_json(retry)}

    def _history(self, body: dict) -> dict:
        entries = self.assistant.history(_player(body), _int(body, "limit", 20))
        return {"items": [_history_json(e) for e in entries]}

    def _send(self, status: int, payload: Any) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        # Jamais le contenu des questions dans les logs (privé).
        log.debug("%s %s", self.address_string(), format % args)


def make_server(assistant: AssistantApi, token: str, host: str, port: int) -> ThreadingHTTPServer:
    if host not in LOOPBACK:
        raise ValueError(f"le cerveau n'écoute qu'en local, pas sur {host!r}")
    handler = type("Handler", (_Handler,), {"assistant": assistant, "token": token})
    server = ThreadingHTTPServer((host, port), handler)
    server.daemon_threads = True
    return server
