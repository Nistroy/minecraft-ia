"""Statut du serveur Minecraft par Server List Ping (protocole 1.7+, minecraft.wiki « Server List Ping »).

Lecture seule, sans console ni RCON : en ligne ?, version, MOTD, joueurs connectés (échantillon vanilla).
"""

from __future__ import annotations

import json
import re
import socket
import struct
from collections.abc import Callable

_FORMAT_CODE = re.compile("§.")
_MAX_PACKET = 1 << 21  # VarInt de longueur de chaîne : 3 octets max


def varint(value: int) -> bytes:
    value &= 0xFFFFFFFF
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def read_varint(read_byte: Callable[[], int]) -> int:
    result = 0
    for shift in range(0, 35, 7):
        byte = read_byte()
        result |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return result - (1 << 32) if result & (1 << 31) else result
    raise ValueError("VarInt trop long")


def _packet(packet_id: int, payload: bytes = b"") -> bytes:
    body = varint(packet_id) + payload
    return varint(len(body)) + body


def _string(text: str) -> bytes:
    data = text.encode()
    return varint(len(data)) + data


def _motd(description: object) -> str:
    if isinstance(description, dict):
        text = str(description.get("text", "")) + "".join(_motd(e) for e in description.get("extra", []))
    else:
        text = str(description or "")
    return _FORMAT_CODE.sub("", text)


def ping(host: str, port: int, timeout: float) -> dict:
    with socket.create_connection((host, port), timeout=timeout) as sock:
        # Version de protocole -1 : convention « je demande juste le statut ».
        handshake = varint(-1) + _string(host) + struct.pack(">H", port) + varint(1)
        sock.sendall(_packet(0, handshake) + _packet(0))
        stream = sock.makefile("rb")

        def read_byte() -> int:
            byte = stream.read(1)
            if not byte:
                raise ConnectionError("connexion fermée")
            return byte[0]

        length = read_varint(read_byte)
        if not 0 < length <= _MAX_PACKET or read_varint(read_byte) != 0:
            raise ValueError("réponse de statut invalide")
        size = read_varint(read_byte)
        data = stream.read(size)
        if len(data) != size:
            raise ConnectionError("réponse tronquée")
    status = json.loads(data)
    if not isinstance(status, dict):
        raise ValueError("réponse de statut invalide")
    return status


def server_status(host: str, port: int, timeout: float = 3.0) -> dict:
    try:
        raw = ping(host, port, timeout)
    except (OSError, ValueError):  # refus, délai, réponse illisible : serveur considéré hors ligne
        return {"online": False}
    players = raw.get("players") if isinstance(raw.get("players"), dict) else {}
    sample = players.get("sample") if isinstance(players.get("sample"), list) else []
    version = raw.get("version") if isinstance(raw.get("version"), dict) else {}
    return {
        "online": True,
        "version": version.get("name"),
        "motd": _motd(raw.get("description")),
        "players_online": players.get("online"),
        "players_max": players.get("max"),
        "players": [p["name"] for p in sample if isinstance(p, dict) and isinstance(p.get("name"), str)],
    }
