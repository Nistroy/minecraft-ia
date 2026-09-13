"""CLI du cerveau : serve, ask, extract, kb index, eval."""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

import httpx

from .assistant import Assistant, Limits
from .config import DEFAULT_CONFIG, Config, ConfigError, ensure_token, load_config, read_secret
from .db import Database
from .evaluation import load_questions, run_eval
from .extract import extract, fetch_vanilla_lang
from .kb import KnowledgeBase
from .llm import LLM, GeminiLLM
from .server import make_server
from .tools import HttpxClient, Toolbox

log = logging.getLogger("minecraft_ia")

CONSOLE_PLAYER = "00000000-0000-0000-0000-000000000001"
LlmFactory = Callable[[Config], Sequence[LLM]]


def gemini_from_config(config: Config) -> list[LLM]:
    """Modèle principal puis modèles de secours, dans l'ordre de la config."""
    key = read_secret(config.gemini_key_file)
    return [GeminiLLM(key, model, config.thinking_level) for model in (config.model, *config.fallback_models)]


def build_assistant(config: Config, db: Database, kb: KnowledgeBase, llms: Sequence[LLM], **limits: int) -> Assistant:
    github_token = read_secret(config.github_token_file) if config.github_token_file else None
    defaults = {
        "questions_per_player_per_day": config.questions_per_player_per_day,
        "llm_calls_per_day": config.llm_calls_per_day,
        "max_tool_rounds": config.max_tool_rounds,
        "max_question_chars": config.max_question_chars,
        "max_answer_chars": config.max_answer_chars,
    }
    return Assistant(
        db,
        kb,
        llms,
        Toolbox(db, kb, HttpxClient(github_token)),
        Limits(**{**defaults, **limits}, display_timezone=config.display_timezone),
    )


def _reindex(db: Database, kb: KnowledgeBase) -> None:
    db.replace_kb_index(kb.documents())


def cmd_kb_index(args: argparse.Namespace, config: Config, db: Database, llm_factory: LlmFactory) -> int:
    kb = KnowledgeBase(config.kb_path, push=config.kb_push)
    kb.write_index()
    _reindex(db, kb)
    print(f"{len(kb.fiches())} fiches, {len(kb.notes())} notes indexées")
    return 0


def cmd_extract(args: argparse.Namespace, config: Config, db: Database, llm_factory: LlmFactory) -> int:
    if config.mods_dir is None and config.vanilla_jar is None:
        raise ConfigError("extract demande mods_dir et/ou vanilla_jar dans la config")
    jars = sorted(config.mods_dir.glob("*.jar")) if config.mods_dir else []
    lang_fr = None
    if config.vanilla_jar is not None and not args.no_vanilla_fr:
        with httpx.Client(timeout=30, follow_redirects=True) as client:
            lang_fr = fetch_vanilla_lang(config.minecraft_version, "fr_fr", client)
    items, recipes = extract(jars, config.vanilla_jar, lang_fr)
    db.replace_exact_data(items, recipes)
    print(f"{len(jars)} jars : {len(items)} noms, {len(recipes)} recettes")
    return 0


def cmd_ask(args: argparse.Namespace, config: Config, db: Database, llm_factory: LlmFactory) -> int:
    kb = KnowledgeBase(config.kb_path, push=config.kb_push)
    reply = build_assistant(config, db, kb, llm_factory(config)).ask(CONSOLE_PLAYER, "console", args.question)
    print(reply.text)
    for source in reply.sources:
        print(f"  source : {source}")
    if reply.status != "ok":
        print(f"  ({reply.status})")
    return 0 if reply.status in ("ok", "unknown") else 1


def cmd_serve(args: argparse.Namespace, config: Config, db: Database, llm_factory: LlmFactory) -> int:
    token = ensure_token(config.token_file)
    kb = KnowledgeBase(config.kb_path, push=config.kb_push)
    _reindex(db, kb)
    server = make_server(build_assistant(config, db, kb, llm_factory(config)), token, config.host, config.port)
    log.info("cerveau prêt sur http://%s:%d", config.host, config.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("arrêt demandé")
    finally:
        server.server_close()
    return 0


def cmd_eval(args: argparse.Namespace, config: Config, db: Database, llm_factory: LlmFactory) -> int:
    questions = load_questions(args.questions)
    kb = KnowledgeBase(config.kb_path, push=config.kb_push)
    _reindex(db, kb)
    assistant = build_assistant(config, db, kb, llm_factory(config), questions_per_player_per_day=len(questions) + 1)
    report = run_eval(assistant, questions)
    for r in report.results:
        print(f"{'✔' if r.passed else '✘'} [{r.status}] {r.question}\n    {r.text}")
    print(
        f"\n{report.correct}/{report.total} justes · {report.unknown} « je sais pas » · {report.invented} invention(s)"
    )
    return 0 if report.invented == 0 else 1


COMMANDS = {"serve": cmd_serve, "ask": cmd_ask, "extract": cmd_extract, "eval": cmd_eval}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="minecraft-ia", description="Cerveau de l'assistant IA en jeu")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help=f"défaut : {DEFAULT_CONFIG}")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("serve", help="API locale pour le mod serveur")
    sub.add_parser("ask", help="pose une question en console").add_argument("question")
    sub.add_parser("extract", help="données exactes depuis les jars").add_argument(
        "--no-vanilla-fr", action="store_true", help="ne pas télécharger les noms FR vanilla"
    )
    kb = sub.add_parser("kb", help="base de connaissances")
    kb.add_subparsers(dest="kb_command", required=True).add_parser("index", help="regénère index.md + index FTS")
    sub.add_parser("eval", help="jeu de questions test").add_argument("questions", type=Path)
    return parser


def main(argv: list[str] | None = None, llm_factory: LlmFactory = gemini_from_config) -> int:
    args = _parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    command = cmd_kb_index if args.command == "kb" else COMMANDS[args.command]
    try:
        config = load_config(args.config)
        config.db_path.parent.mkdir(parents=True, exist_ok=True)
        db = Database(config.db_path)
        try:
            return command(args, config, db, llm_factory)
        finally:
            db.close()
    except ConfigError as e:
        print(f"erreur de config : {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
