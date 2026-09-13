"""Jeu de questions test : mesure % justes, % « je sais pas », inventions (doit rester à 0)."""

from __future__ import annotations

import tomllib
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .assistant import Reply

EVAL_PLAYER = "00000000-0000-0000-0000-000000000000"


class Asker(Protocol):
    def ask(self, player: str, player_name: str, question: str) -> Reply: ...


@dataclass(frozen=True)
class EvalQuestion:
    text: str
    expected: list[str]
    expect_unknown: bool


@dataclass(frozen=True)
class EvalResult:
    question: str
    passed: bool
    status: str
    text: str


@dataclass(frozen=True)
class EvalReport:
    results: list[EvalResult]
    total: int
    correct: int
    unknown: int
    invented: int


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def load_questions(path: Path) -> list[EvalQuestion]:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    return [
        EvalQuestion(q["texte"], list(q.get("attendu", [])), bool(q.get("sais_pas", False)))
        for q in data.get("question", [])
    ]


def run_eval(assistant: Asker, questions: list[EvalQuestion]) -> EvalReport:
    results, invented = [], 0
    for q in questions:
        reply = assistant.ask(EVAL_PLAYER, "eval", q.text)
        if q.expect_unknown:
            passed = reply.status == "unknown"
            invented += reply.status == "ok"
        else:
            text = _normalize(reply.text)
            passed = reply.status == "ok" and all(_normalize(k) in text for k in q.expected)
        results.append(EvalResult(q.text, passed, reply.status, reply.text))
    return EvalReport(
        results, len(results), sum(r.passed for r in results), sum(r.status == "unknown" for r in results), invented
    )
