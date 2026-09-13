"""Base de connaissances : fiches + notes md dans un dépôt git. L'IA commit, nistroy édite/revert."""

from __future__ import annotations

import hashlib
import logging
import re
import subprocess
import threading
from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import yaml

from .db import KbDoc

log = logging.getLogger(__name__)

AUTHOR = "minecraft-ia <minecraft-ia@users.noreply.github.com>"
GENERAL = "_general"
_SLUG = re.compile(r"^(_general|[a-z0-9][a-z0-9_.-]{0,63})$")
_NOTE_PATH = re.compile(r"^notes/(_general|[a-z0-9][a-z0-9_.-]{0,63})/\d{4}-\d{2}-\d{2}-[0-9a-f]{8}\.md$")


class NoteStatus(StrEnum):
    UNVERIFIED = "non-vérifié"
    PLAYER_CONFIRMED = "confirmé-joueur"
    NISTROY_VALIDATED = "validé-nistroy"
    CONTESTED = "contesté"


@dataclass(frozen=True)
class Fiche:
    slug: str
    path: str
    meta: dict
    body: str


@dataclass(frozen=True)
class Note:
    path: str
    meta: dict
    body: str


def _read_frontmatter(path: Path) -> tuple[dict, str] | None:
    """Frontmatter YAML + corps. None si YAML invalide : fichier ignoré, jamais de crash du cerveau."""
    text = path.read_text(encoding="utf-8")
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            try:
                meta = yaml.safe_load(text[4:end]) or {}
            except yaml.YAMLError:
                log.warning("frontmatter invalide, fichier ignoré : %s", path)
                return None
            return (meta if isinstance(meta, dict) else {}), text[end + 5 :]
    return {}, text


def _render(meta: dict, body: str) -> str:
    front = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True)
    return f"---\n{front}---\n{body.rstrip()}\n"


class Git:
    def __init__(self, root: Path, push: bool) -> None:
        self._root = root
        self._push = push

    def commit(self, paths: list[str], message: str) -> None:
        self._run("add", "--", *paths)
        if self._run("diff", "--cached", "--quiet", "--", *paths, check=False).returncode == 0:
            return
        self._run("commit", "-q", "-m", message, f"--author={AUTHOR}", "--", *paths)
        if self._push:
            result = self._run("push", "-q", check=False)
            if result.returncode != 0:
                log.warning("git push de la base de connaissances échoué : %s", result.stderr.strip())

    def _run(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", "-C", str(self._root), *args], check=check, capture_output=True, text=True, timeout=60
        )


class KnowledgeBase:
    def __init__(self, root: Path, push: bool = False) -> None:
        self.root = root
        self._git = Git(root, push)
        self._lock = threading.Lock()

    # --- lecture ----------------------------------------------------------------------------------

    def fiches(self) -> list[Fiche]:
        return [f for p in sorted((self.root / "mods").glob("*.md")) if (f := self.fiche(p.stem))]

    def fiche(self, slug: str) -> Fiche | None:
        if not _SLUG.match(slug) or slug == GENERAL:
            return None
        path = self.root / "mods" / f"{slug}.md"
        if not path.is_file():
            return None
        parsed = _read_frontmatter(path)
        return Fiche(slug, f"mods/{slug}.md", *parsed) if parsed else None

    def notes(self) -> list[Note]:
        return [
            n
            for p in sorted((self.root / "notes").glob("*/*.md"))
            if (n := self.note(p.relative_to(self.root).as_posix()))
        ]

    def note(self, rel_path: str) -> Note | None:
        if not _NOTE_PATH.match(rel_path):
            return None
        path = self.root / rel_path
        if not path.is_file():
            return None
        parsed = _read_frontmatter(path)
        return Note(rel_path, *parsed) if parsed else None

    def documents(self) -> Iterator[KbDoc]:
        for f in self.fiches():
            title = f"{f.meta.get('nom', f.slug)} — {f.meta.get('resume', '')}"
            yield KbDoc(f.path, f.slug, "fiche", title, f.body)
        for n in self.notes():
            m = n.meta
            title = f"note {m.get('statut')} ({m.get('mod')} {m.get('version', '')}, {m.get('date')})"
            yield KbDoc(n.path, str(m.get("mod", GENERAL)), "note", title, f"{n.body}\nsource : {m.get('source')}")

    # --- écriture (toujours un commit) ------------------------------------------------------------

    def add_note(
        self, mod: str, fact: str, source: str, version: str, today: str, answer_id: int | None = None
    ) -> Note:
        fact, source = fact.strip(), source.strip()
        if not _SLUG.match(mod):
            raise ValueError(f"mod invalide : {mod!r}")
        if not fact or not source:
            raise ValueError("une note demande un fait et une source")
        digest = hashlib.sha1(f"{mod}\n{fact}".encode(), usedforsecurity=False).hexdigest()[:8]
        rel_path = f"notes/{mod}/{today}-{digest}.md"
        meta = {"mod": mod, "version": version, "statut": NoteStatus.UNVERIFIED.value, "source": source, "date": today}
        if answer_id is not None:
            meta["reponse"] = answer_id
        with self._lock:
            path = self.root / rel_path
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(_render(meta, fact), encoding="utf-8")
                self._git.commit([rel_path], f"note({mod}): {fact[:60]}")
        return self.note(rel_path)

    def set_note_status(self, rel_path: str, status: NoteStatus, reason: str) -> bool:
        """Change le statut. Une note validée par nistroy n'est jamais modifiée par un vote."""
        with self._lock:
            note = self.note(rel_path)
            if note is None:
                return False
            current = note.meta.get("statut")
            if current == NoteStatus.NISTROY_VALIDATED or current == status:
                return False
            meta = {**note.meta, "statut": status.value}
            (self.root / rel_path).write_text(_render(meta, note.body), encoding="utf-8")
            self._git.commit([rel_path], f"note({meta.get('mod')}): {status.value} ({reason})")
            return True

    def write_index(self) -> Path:
        lines = ["# Index des mods", "", "Généré par `minecraft-ia kb index` depuis les fiches. Ne pas éditer.", ""]
        for f in self.fiches():
            namespaces = ", ".join(f.meta.get("namespaces") or [])
            lines.append(f"- `{f.slug}` — {f.meta.get('nom', f.slug)} — {f.meta.get('resume', '')} — ns: {namespaces}")
        path = self.root / "index.md"
        with self._lock:
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            self._git.commit(["index.md"], "docs(index): regénère l'index des mods")
        return path
