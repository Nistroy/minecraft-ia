"""Seul module d'accès à SQLite : historique, compteurs, données exactes, index de recherche.

Changer de moteur (ex. Postgres) = réécrire ce module seulement.
"""

from __future__ import annotations

import json
import re
import sqlite3
import threading
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path

_WORD = re.compile(r"\w+", re.UNICODE)


@dataclass(frozen=True)
class Item:
    id: str
    mod: str
    kind: str  # item / block / entity
    name_en: str | None
    name_fr: str | None


@dataclass(frozen=True)
class Recipe:
    id: str
    mod: str
    type: str
    result: str | None
    inputs: list[str]
    json: str


@dataclass(frozen=True)
class KbDoc:
    path: str
    slug: str
    kind: str
    title: str
    body: str


@dataclass(frozen=True)
class KbHit:
    path: str
    slug: str
    kind: str
    title: str
    snippet: str


@dataclass(frozen=True)
class AnswerRow:
    id: int
    question_id: int
    player: str
    question: str
    text: str
    sources: list[str]
    status: str
    notes: list[str]


@dataclass(frozen=True)
class HistoryEntry:
    answer_id: int
    question: str
    text: str
    sources: list[str]
    status: str
    vote: bool | None
    asked_at: str


def fts_query(text: str) -> str:
    """Texte libre (joueur ou LLM) → requête FTS5 sûre : mots entre guillemets, OR, classés par bm25."""
    return " OR ".join(f'"{word}"' for word in _WORD.findall(text))


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _item(row: sqlite3.Row) -> Item:
    return Item(row["id"], row["mod"], row["kind"], row["name_en"], row["name_fr"])


class Database:
    def __init__(self, path: Path | str) -> None:
        # Un seul écrivain (le cerveau) mais plusieurs threads HTTP : une connexion + un verrou.
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._lock = threading.Lock()
        self._migrate()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # --- migrations -------------------------------------------------------------------------------

    def schema_version(self) -> int:
        with self._lock:
            return self._conn.execute("PRAGMA user_version").fetchone()[0]

    def _migrate(self) -> None:
        current = self._conn.execute("PRAGMA user_version").fetchone()[0]
        folder = resources.files("minecraft_ia") / "migrations"
        for script in sorted(folder.iterdir(), key=lambda p: p.name):
            if not script.name.endswith(".sql"):
                continue
            number = int(script.name.split("_", 1)[0])
            if number <= current:
                continue
            sql = script.read_text(encoding="utf-8")
            self._conn.executescript(f"BEGIN;\n{sql}\nPRAGMA user_version = {number};\nCOMMIT;")

    # --- historique -------------------------------------------------------------------------------

    def add_question(self, player: str, player_name: str, text: str, day: str) -> int:
        with self._lock, self._conn:
            cursor = self._conn.execute(
                "INSERT INTO question (player, player_name, text, asked_at, day) VALUES (?, ?, ?, ?, ?)",
                (player, player_name, text, _now(), day),
            )
            return cursor.lastrowid

    def add_answer(
        self,
        question_id: int,
        text: str,
        sources: list[str],
        status: str,
        llm_calls: int,
        notes: list[str],
        retry_of: int | None = None,
    ) -> int:
        with self._lock, self._conn:
            cursor = self._conn.execute(
                "INSERT INTO answer (question_id, text, sources, notes, status, llm_calls, retry_of, answered_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (question_id, text, json.dumps(sources), json.dumps(notes), status, llm_calls, retry_of, _now()),
            )
            return cursor.lastrowid

    def answer(self, answer_id: int) -> AnswerRow | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT a.id, a.question_id, q.player, q.text AS question, a.text, a.sources, a.status, a.notes"
                " FROM answer a JOIN question q ON q.id = a.question_id WHERE a.id = ?",
                (answer_id,),
            ).fetchone()
        if row is None:
            return None
        return AnswerRow(
            row["id"],
            row["question_id"],
            row["player"],
            row["question"],
            row["text"],
            json.loads(row["sources"]),
            row["status"],
            json.loads(row["notes"]),
        )

    def has_retry(self, answer_id: int) -> bool:
        with self._lock:
            return self._conn.execute("SELECT 1 FROM answer WHERE retry_of = ?", (answer_id,)).fetchone() is not None

    def add_vote(self, answer_id: int, player: str, up: bool) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO vote (answer_id, player, up, voted_at) VALUES (?, ?, ?, ?)"
                " ON CONFLICT (answer_id, player) DO UPDATE SET up = excluded.up, voted_at = excluded.voted_at",
                (answer_id, player, int(up), _now()),
            )

    def history(self, player: str, limit: int) -> list[HistoryEntry]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT a.id, q.text AS question, a.text, a.sources, a.status, v.up, q.asked_at"
                " FROM answer a JOIN question q ON q.id = a.question_id"
                " LEFT JOIN vote v ON v.answer_id = a.id AND v.player = q.player"
                " WHERE q.player = ? ORDER BY a.id DESC LIMIT ?",
                (player, limit),
            ).fetchall()
        return [
            HistoryEntry(
                r["id"],
                r["question"],
                r["text"],
                json.loads(r["sources"]),
                r["status"],
                None if r["up"] is None else bool(r["up"]),
                r["asked_at"],
            )
            for r in rows
        ]

    # --- quotas -----------------------------------------------------------------------------------

    def questions_on(self, player: str, day: str) -> int:
        with self._lock:
            return self._conn.execute(
                "SELECT count(*) FROM question WHERE player = ? AND day = ?", (player, day)
            ).fetchone()[0]

    def add_llm_calls(self, day: str, calls: int) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO llm_usage (day, calls) VALUES (?, ?)"
                " ON CONFLICT (day) DO UPDATE SET calls = calls + excluded.calls",
                (day, calls),
            )

    def llm_calls_on(self, day: str) -> int:
        with self._lock:
            row = self._conn.execute("SELECT calls FROM llm_usage WHERE day = ?", (day,)).fetchone()
        return row[0] if row else 0

    # --- données exactes --------------------------------------------------------------------------

    def replace_exact_data(self, items: Iterable[Item], recipes: Iterable[Recipe]) -> None:
        with self._lock, self._conn:
            for table in ("recipe_input", "recipe", "item", "item_fts"):
                self._conn.execute(f"DELETE FROM {table}")  # noqa: S608 — noms de tables fixes
            self._conn.executemany(
                "INSERT OR REPLACE INTO item (id, kind, mod, name_en, name_fr) VALUES (?, ?, ?, ?, ?)",
                [(i.id, i.kind, i.mod, i.name_en, i.name_fr) for i in items],
            )
            self._conn.execute(
                "INSERT INTO item_fts (id, kind, name_en, name_fr) SELECT id, kind, name_en, name_fr FROM item"
            )
            for recipe in recipes:
                self._conn.execute(
                    "INSERT OR REPLACE INTO recipe VALUES (?, ?, ?, ?, ?)",
                    (recipe.id, recipe.mod, recipe.type, recipe.result, recipe.json),
                )
                self._conn.executemany(
                    "INSERT OR IGNORE INTO recipe_input VALUES (?, ?)", [(recipe.id, i) for i in recipe.inputs]
                )

    def item(self, item_id: str) -> Item | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM item WHERE id = ?"
                " ORDER BY CASE kind WHEN 'item' THEN 0 WHEN 'block' THEN 1 ELSE 2 END LIMIT 1",
                (item_id,),
            ).fetchone()
        return _item(row) if row else None

    def find_items(self, query: str, limit: int) -> list[Item]:
        match = fts_query(query)
        if not match:
            return []
        with self._lock:
            rows = self._conn.execute(
                "SELECT i.* FROM item_fts f JOIN item i ON i.id = f.id AND i.kind = f.kind"
                " WHERE item_fts MATCH ? ORDER BY bm25(item_fts) LIMIT ?",
                (match, limit),
            ).fetchall()
        return [_item(r) for r in rows]

    def recipes_producing(self, item_id: str, limit: int) -> list[Recipe]:
        return self._recipes("SELECT * FROM recipe WHERE result = ? ORDER BY id LIMIT ?", item_id, limit)

    def recipes_using(self, item_or_tag: str, limit: int) -> list[Recipe]:
        return self._recipes(
            "SELECT * FROM recipe WHERE id IN (SELECT recipe_id FROM recipe_input WHERE input = ?) ORDER BY id LIMIT ?",
            item_or_tag,
            limit,
        )

    def _recipes(self, sql: str, value: str, limit: int) -> list[Recipe]:
        with self._lock:
            rows = self._conn.execute(sql, (value, limit)).fetchall()
            inputs = {
                r["id"]: [
                    i[0]
                    for i in self._conn.execute(
                        "SELECT input FROM recipe_input WHERE recipe_id = ? ORDER BY input", (r["id"],)
                    )
                ]
                for r in rows
            }
        return [Recipe(r["id"], r["mod"], r["type"], r["result"], inputs[r["id"]], r["json"]) for r in rows]

    # --- index des connaissances ------------------------------------------------------------------

    def replace_kb_index(self, docs: Iterable[KbDoc]) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM kb_fts")
            self._conn.executemany(
                "INSERT INTO kb_fts (path, slug, kind, title, body) VALUES (?, ?, ?, ?, ?)",
                [(d.path, d.slug, d.kind, d.title, d.body) for d in docs],
            )

    def search_kb(self, query: str, limit: int) -> list[KbHit]:
        match = fts_query(query)
        if not match:
            return []
        with self._lock:
            rows = self._conn.execute(
                "SELECT path, slug, kind, title, snippet(kb_fts, 4, '', '', '…', 24) AS snippet"
                " FROM kb_fts WHERE kb_fts MATCH ? ORDER BY bm25(kb_fts) LIMIT ?",
                (match, limit),
            ).fetchall()
        return [KbHit(r["path"], r["slug"], r["kind"], r["title"], r["snippet"]) for r in rows]
