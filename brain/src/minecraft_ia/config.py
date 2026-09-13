"""Configuration du cerveau (TOML) + secrets (fichiers hors dépôt, jamais affichés)."""

from __future__ import annotations

import os
import secrets
import tomllib
from dataclasses import dataclass, fields
from pathlib import Path

CONFIG_DIR = Path("~/.config/minecraft-ia").expanduser()
DEFAULT_CONFIG = CONFIG_DIR / "config.toml"
LOOPBACK = frozenset({"127.0.0.1", "::1", "localhost"})
THINKING_LEVELS = frozenset({"low", "medium", "high"})


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Config:
    kb_path: Path
    db_path: Path
    gemini_key_file: Path = CONFIG_DIR / "gemini-key"
    token_file: Path = CONFIG_DIR / "brain-token"
    github_token_file: Path | None = None
    mods_dir: Path | None = None
    vanilla_jar: Path | None = None
    minecraft_version: str = "1.21.1"
    model: str = "gemini-3.8-flash"
    # Essayés dans l'ordre si le principal est saturé (503) ou à court de quota (429) ; quotas gratuits par modèle.
    fallback_models: tuple[str, ...] = ("gemini-3.7-flash", "gemini-3.5-flash")
    thinking_level: str = "high"
    host: str = "127.0.0.1"
    port: int = 8765
    # Défauts prudents : à caler sur la limite « requests per day » affichée dans AI Studio.
    questions_per_player_per_day: int = 20
    llm_calls_per_day: int = 200
    max_tool_rounds: int = 8
    max_question_chars: int = 256
    max_answer_chars: int = 1200
    kb_push: bool = False
    display_timezone: str = "Europe/Paris"


_PATHS = {"kb_path", "db_path", "gemini_key_file", "token_file", "github_token_file", "mods_dir", "vanilla_jar"}
_POSITIVE_INTS = {
    "port",
    "questions_per_player_per_day",
    "llm_calls_per_day",
    "max_tool_rounds",
    "max_question_chars",
    "max_answer_chars",
}


def load_config(path: Path = DEFAULT_CONFIG) -> Config:
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as e:
        raise ConfigError(f"config illisible : {path} ({e})") from e
    known = {f.name for f in fields(Config)}
    unknown = set(raw) - known
    if unknown:
        raise ConfigError(f"clés inconnues dans {path} : {', '.join(sorted(unknown))}")
    for required in ("kb_path", "db_path"):
        if required not in raw:
            raise ConfigError(f"clé obligatoire manquante dans {path} : {required}")
    values = {}
    for key, value in raw.items():
        if key in _PATHS:
            if not isinstance(value, str):
                raise ConfigError(f"{key} doit être un chemin (texte)")
            p = Path(value).expanduser()
            values[key] = p if p.is_absolute() else path.parent / p
        elif key in _POSITIVE_INTS:
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise ConfigError(f"{key} doit être un entier > 0")
            values[key] = value
        elif key == "fallback_models":
            if not isinstance(value, list) or not all(isinstance(m, str) and m.strip() for m in value):
                raise ConfigError("fallback_models doit être une liste de noms de modèles")
            values[key] = tuple(m.strip() for m in value)
        else:
            values[key] = value
    config = Config(**values)
    if config.host not in LOOPBACK:
        raise ConfigError(f"host doit être local ({', '.join(sorted(LOOPBACK))}) : jamais exposé au tunnel")
    if config.thinking_level not in THINKING_LEVELS:
        raise ConfigError(f"thinking_level doit être dans {sorted(THINKING_LEVELS)}")
    if not isinstance(config.kb_push, bool):
        raise ConfigError("kb_push doit être true/false")
    return config


def read_secret(path: Path) -> str:
    """Lit un secret. Le message d'erreur donne le chemin, jamais le contenu."""
    try:
        value = path.read_text(encoding="utf-8").strip()
    except OSError as e:
        raise ConfigError(f"secret introuvable : {path}") from e
    if not value:
        raise ConfigError(f"secret vide : {path}")
    return value


def ensure_token(path: Path) -> str:
    """Jeton partagé cerveau ↔ mod serveur ; créé (0600) au premier lancement."""
    if path.exists():
        return read_secret(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    token = secrets.token_urlsafe(32)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(token + "\n")
    return token
