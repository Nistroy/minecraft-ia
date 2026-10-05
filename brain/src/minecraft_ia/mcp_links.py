"""Liens secrets du MCP : 1 par joueur, révocable sans redémarrer. URL = `https://<hôte>/<jeton>/mcp`, ou
`https://<hôte>/mcp` + `Authorization: Bearer <jeton>` (CLI lancée par le mod).

Le fichier (0600) ne garde que l'empreinte SHA-256 de chaque jeton : le jeton n'est affiché qu'une fois, à la création.
Révoquer laisse une marque : le mod ne peut plus réattribuer de lien à ce joueur tant que nistroy ne le recrée pas.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import threading
from pathlib import Path

_NAME = re.compile(r"^[a-z0-9_-]{1,32}$")
_REVOKED = "revoked"


class LinkError(Exception):
    pass


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class LinkStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()
        self._cache: tuple[tuple[int, int, int] | None, dict[str, str]] = (None, {})

    def _load(self) -> dict[str, str]:
        """Relu dès que le fichier change (inode, taille, date) : ajout et révocation pris en compte à chaud."""
        try:
            st = self.path.stat()
        except FileNotFoundError:
            return {}
        key = (st.st_ino, st.st_size, st.st_mtime_ns)
        with self._lock:
            if self._cache[0] == key:
                return self._cache[1]
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as e:
                raise LinkError(f"fichier de liens illisible : {self.path}") from e
            if not isinstance(data, dict) or not all(isinstance(v, str) for v in data.values()):
                raise LinkError(f"fichier de liens invalide : {self.path}")
            self._cache = (key, data)
            return data

    def _save(self, links: dict[str, str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(links, f, indent=2, sort_keys=True)
        os.replace(tmp, self.path)

    def match(self, token: str) -> str | None:
        if not token:
            return None
        digest = _digest(token)
        for name, stored in self._load().items():
            if stored != _REVOKED and hmac.compare_digest(stored, digest):
                return name
        return None

    def names(self) -> list[str]:
        return sorted(name for name, stored in self._load().items() if stored != _REVOKED)

    def add(self, name: str) -> str:
        """Création à la main (nistroy) ; rouvre aussi l'accès d'un joueur révoqué."""
        if name in self.names():
            raise LinkError(f"lien déjà existant pour {name} (le révoquer d'abord)")
        return self._issue(name)

    def provision(self, name: str) -> str:
        """Lien demandé par le mod pour un joueur connecté : nouveau jeton, l'ancien ne marche plus."""
        if self._load().get(name) == _REVOKED:
            raise LinkError(f"accès MCP coupé pour {name}")
        return self._issue(name)

    def revoke(self, name: str) -> None:
        if name not in self.names():
            raise LinkError(f"aucun lien pour {name}")
        self._save({**self._load(), name: _REVOKED})

    def _issue(self, name: str) -> str:
        if not _NAME.match(name):
            raise LinkError("nom attendu : 1 à 32 caractères a-z 0-9 _ -")
        token = secrets.token_urlsafe(32)
        self._save({**self._load(), name: _digest(token)})
        return token
