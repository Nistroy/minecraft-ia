"""Outils du LLM : connaissances locales, données exactes, Modrinth, GitHub.

Chaque résultat porte un identifiant `source` ; seules les sources vues ici peuvent être citées.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from .db import Database
from .kb import KnowledgeBase
from .llm import ToolCall, ToolSpec

_SLUG = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
_REPO = re.compile(r"^[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$")
_RESOURCE_ID = re.compile(r"^#?[a-z0-9_.-]+:[a-z0-9_./-]+$")
USER_AGENT = "Nistroy/minecraft-ia (https://github.com/Nistroy/minecraft-ia)"


class Http(Protocol):
    def get_json(self, url: str, params: dict | None = None) -> Any: ...
    def get_text(self, url: str) -> str: ...


class HttpxClient:
    def __init__(self, github_token: str | None = None, timeout: float = 15.0) -> None:
        self._client = httpx.Client(timeout=timeout, follow_redirects=True, headers={"User-Agent": USER_AGENT})
        self._github_token = github_token

    def _headers(self, url: str, raw: bool = False) -> dict:
        headers = {}
        if url.startswith("https://api.github.com/"):
            headers["Accept"] = "application/vnd.github.raw+json" if raw else "application/vnd.github+json"
            if self._github_token:
                headers["Authorization"] = f"Bearer {self._github_token}"
        return headers

    def get_json(self, url: str, params: dict | None = None) -> Any:
        response = self._client.get(url, params=params, headers=self._headers(url))
        response.raise_for_status()
        return response.json()

    def get_text(self, url: str) -> str:
        response = self._client.get(url, headers=self._headers(url, raw=True))
        response.raise_for_status()
        return response.text


@dataclass(frozen=True)
class PendingNote:
    mod: str
    fact: str
    source: str


@dataclass
class ToolContext:
    """État d'une recherche : sources vues (seules citables) et notes à écrire après la réponse."""

    seen: set[str] = field(default_factory=set)
    pending_notes: list[PendingNote] = field(default_factory=list)


class BadArgs(ValueError):
    pass


def _text(args: dict, key: str, max_len: int, default: str | None = None) -> str:
    value = args.get(key, default)
    if not isinstance(value, str) or not value.strip():
        raise BadArgs(f"argument `{key}` manquant ou vide")
    return value.strip()[:max_len]


def _jsonable(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, ensure_ascii=False))


def _obj(properties: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": properties, "required": required}


_STR = {"type": "string"}

SPECS = [
    ToolSpec(
        "search_knowledge",
        "Recherche plein texte dans les fiches des mods du serveur et les notes apprises. À utiliser en premier.",
        _obj({"query": _STR}, ["query"]),
    ),
    ToolSpec(
        "read_fiche",
        "Lit la fiche complète d'un mod (slug Modrinth, voir search_knowledge).",
        _obj({"slug": _STR}, ["slug"]),
    ),
    ToolSpec(
        "find_item",
        "Cherche un item, bloc ou mob par nom (FR ou EN) ou id dans les données exactes extraites des jars du serveur.",
        _obj({"name": _STR}, ["name"]),
    ),
    ToolSpec(
        "item_recipes",
        "Recettes exactes qui produisent (produce) ou utilisent (use) un item. item_id = ns:id ou #tag.",
        _obj({"item_id": _STR, "direction": {"type": "string", "enum": ["produce", "use"]}}, ["item_id"]),
    ),
    ToolSpec(
        "modrinth_project",
        "Page Modrinth d'un mod : description, liens wiki/source/issues, version installée sur le serveur.",
        _obj({"slug": _STR}, ["slug"]),
    ),
    ToolSpec(
        "github_readme",
        "README d'un dépôt GitHub (owner/nom), ex. depuis source_url de Modrinth.",
        _obj({"repo": _STR}, ["repo"]),
    ),
    ToolSpec(
        "github_issues",
        "Cherche dans les issues GitHub d'un dépôt (bugs connus, questions).",
        _obj({"repo": _STR, "query": _STR}, ["repo", "query"]),
    ),
    ToolSpec(
        "save_note",
        "Enregistre un fait appris sur le web, absent des fiches, avec sa source exacte "
        "(URL déjà vue). mod = slug Modrinth ou _general.",
        _obj({"mod": _STR, "fact": _STR, "source": _STR}, ["mod", "fact", "source"]),
    ),
    ToolSpec(
        "answer",
        "Réponse finale au joueur. sources = identifiants `source` exacts des résultats utilisés. "
        "unknown=true si rien de fiable trouvé.",
        _obj(
            {"text": _STR, "sources": {"type": "array", "items": _STR}, "unknown": {"type": "boolean"}},
            ["text", "sources"],
        ),
    ),
]


class Toolbox:
    def __init__(self, db: Database, kb: KnowledgeBase, http: Http) -> None:
        self._db = db
        self._kb = kb
        self._http = http
        self._handlers: dict[str, Callable[[dict, ToolContext], dict]] = {
            "search_knowledge": self._search_knowledge,
            "read_fiche": self._read_fiche,
            "find_item": self._find_item,
            "item_recipes": self._item_recipes,
            "modrinth_project": self._modrinth_project,
            "github_readme": self._github_readme,
            "github_issues": self._github_issues,
            "save_note": self._save_note,
        }

    def specs(self) -> list[ToolSpec]:
        return SPECS

    def run(self, call: ToolCall, ctx: ToolContext) -> dict:
        handler = self._handlers.get(call.name)
        if handler is None:
            return {"error": f"outil inconnu : {call.name}"}
        try:
            return handler(call.args, ctx)
        except BadArgs as e:
            return {"error": str(e)}
        except (httpx.HTTPError, KeyError, ValueError) as e:
            return {"error": f"échec : {type(e).__name__}"}

    # --- connaissances locales --------------------------------------------------------------------

    def _search_knowledge(self, args: dict, ctx: ToolContext) -> dict:
        results = []
        for hit in self._db.search_kb(_text(args, "query", 200), limit=8):
            if hit.kind == "note":
                note = self._kb.note(hit.path)
                source = f"note:{hit.path}"
                extract = f"{note.body.strip()} (statut : {note.meta.get('statut')})" if note else hit.snippet
            else:
                source, extract = f"kb:{hit.path}", hit.snippet
            ctx.seen.add(source)
            results.append(
                {"source": source, "kind": hit.kind, "slug": hit.slug, "title": hit.title, "extract": extract}
            )
        return {"results": results}

    def _read_fiche(self, args: dict, ctx: ToolContext) -> dict:
        fiche = self._kb.fiche(_text(args, "slug", 64))
        if fiche is None:
            return {"error": "fiche inconnue (voir search_knowledge)"}
        source = f"kb:{fiche.path}"
        ctx.seen.add(source)
        return {"source": source, "meta": _jsonable(fiche.meta), "content": fiche.body[:12000]}

    # --- données exactes --------------------------------------------------------------------------

    def _find_item(self, args: dict, ctx: ToolContext) -> dict:
        items = []
        for item in self._db.find_items(_text(args, "name", 100), limit=10):
            source = f"data:item:{item.id}"
            ctx.seen.add(source)
            items.append(
                {
                    "source": source,
                    "id": item.id,
                    "kind": item.kind,
                    "mod": item.mod,
                    "name_fr": item.name_fr,
                    "name_en": item.name_en,
                }
            )
        return {"items": items}

    def _item_recipes(self, args: dict, ctx: ToolContext) -> dict:
        item_id = _text(args, "item_id", 120)
        if not _RESOURCE_ID.match(item_id):
            raise BadArgs("item_id attendu : ns:id ou #tag")
        direction = args.get("direction", "produce")
        if direction == "use":
            recipes = self._db.recipes_using(item_id, limit=10)
        else:
            recipes = self._db.recipes_producing(item_id, limit=10)
        out = []
        for r in recipes:
            source = f"data:recipe:{r.id}"
            ctx.seen.add(source)
            out.append(
                {
                    "source": source,
                    "id": r.id,
                    "mod": r.mod,
                    "type": r.type,
                    "result": r.result,
                    "inputs": r.inputs,
                    "json": r.json[:1500],
                }
            )
        return {"recipes": out}

    # --- web (API ciblées, versions vérifiables) --------------------------------------------------

    def _modrinth_project(self, args: dict, ctx: ToolContext) -> dict:
        slug = _text(args, "slug", 64)
        if not _SLUG.match(slug):
            raise BadArgs("slug invalide")
        project = self._http.get_json(f"https://api.modrinth.com/v2/project/{slug}")
        fiche = self._kb.fiche(slug.lower())
        source = f"https://modrinth.com/mod/{project.get('slug', slug)}"
        ctx.seen.add(source)
        return {
            "source": source,
            "title": project.get("title"),
            "description": project.get("description"),
            "body": (project.get("body") or "")[:6000],
            "wiki_url": project.get("wiki_url"),
            "source_url": project.get("source_url"),
            "issues_url": project.get("issues_url"),
            "installed_version": fiche.meta.get("version") if fiche else None,
        }

    def _github_readme(self, args: dict, ctx: ToolContext) -> dict:
        repo = self._repo(args)
        content = self._http.get_text(f"https://api.github.com/repos/{repo}/readme")
        source = f"https://github.com/{repo}"
        ctx.seen.add(source)
        return {"source": source, "content": content[:8000]}

    def _github_issues(self, args: dict, ctx: ToolContext) -> dict:
        repo = self._repo(args)
        query = _text(args, "query", 150)
        found = self._http.get_json(
            "https://api.github.com/search/issues", params={"q": f"repo:{repo} is:issue {query}", "per_page": 5}
        )
        issues = []
        for item in found.get("items", [])[:5]:
            url = item.get("html_url", "")
            if url.startswith(f"https://github.com/{repo}/"):
                ctx.seen.add(url)
                issues.append(
                    {
                        "source": url,
                        "title": item.get("title"),
                        "state": item.get("state"),
                        "body": (item.get("body") or "")[:800],
                    }
                )
        return {"issues": issues}

    @staticmethod
    def _repo(args: dict) -> str:
        repo = _text(args, "repo", 201).removeprefix("https://github.com/").strip("/")
        if not _REPO.match(repo) or ".." in repo:
            raise BadArgs("repo attendu : owner/nom")
        return repo

    # --- apprentissage ----------------------------------------------------------------------------

    def _save_note(self, args: dict, ctx: ToolContext) -> dict:
        source = _text(args, "source", 300)
        if source not in ctx.seen or not source.startswith("https://"):
            return {"error": "source refusée : doit être une URL déjà renvoyée par un outil web"}
        ctx.pending_notes.append(PendingNote(_text(args, "mod", 64), _text(args, "fact", 500), source))
        return {"saved": True}
