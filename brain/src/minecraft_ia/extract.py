"""Extraction des données exactes des jars : noms FR/EN (items, blocs, mobs), recettes et fichiers texte de `data/`
(tables de loot, tags, worldgen…) ; plus les configs du serveur, sans les fichiers qui contiennent un secret.

Résultat en SQLite local seulement : contenu des mods, jamais commité ni redistribué.
"""

from __future__ import annotations

import io
import json
import logging
import re
import zipfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from .db import GameFile, Item, Recipe

log = logging.getLogger(__name__)

_LANG_FILE = re.compile(r"^assets/[^/]+/lang/(en_us|fr_fr)\.json$")
# Sans point dans namespace ni chemin : `block.minecraft.banner.border.light_blue`, `item.x.sword.desc` = sous-clés.
_LANG_KEY = re.compile(r"^(item|block|entity)\.([a-z0-9_-]+)\.([a-z0-9_/-]+)$")
_RECIPE_FILE = re.compile(r"^data/([a-z0-9_.-]+)/recipe/([a-z0-9_./-]+)\.json$")
_NESTED_JAR = re.compile(r"^META-INF/jars/[^/]+\.jar$")
_VANILLA_INNER = re.compile(r"^META-INF/versions/[^/]+/server-[^/]+\.jar$")
_INGREDIENT_KEYS = ("key", "ingredients", "ingredient", "base", "addition", "template")
_LANG_FIELD = {"en_us": "en", "fr_fr": "fr"}
_DATA_TEXT = re.compile(r"^data/[a-z0-9_.-]+/\S+\.(json|mcfunction|txt)$")
MAX_FILE_BYTES = 1_000_000
_CONFIG_SUFFIXES = frozenset({".json", ".json5", ".toml", ".yaml", ".yml", ".properties", ".cfg", ".txt", ".snbt"})
# Clé de secret (`password`, `tokenFile`, `Discord_Token`, `rcon.password`…) → fichier exclu en entier.
# Les mots seulement en valeur (`"name": "Secret Room"`) ou au milieu d'un chemin ne comptent pas.
_SECRET_KEY = re.compile(
    r"""(?:^|[{,\s])["']?[\w.-]*(?:token|password|passwd|secret|api_?key|webhook)\w*["']?\s*[:=]""", re.I | re.M
)
_SECRET_NAME = re.compile(r"token|secret|password|credential", re.I)


@dataclass(frozen=True)
class Extracted:
    items: list[Item]
    recipes: list[Recipe]
    files: list[GameFile]
    mods: list[tuple[str, str | None]]  # jars de premier niveau : (id, version)


class _Collector:
    def __init__(self) -> None:
        self.names: dict[tuple[str, str], dict[str, str | None]] = {}
        self.recipes: dict[str, Recipe] = {}
        self.files: dict[tuple[str, str], GameFile] = {}
        self.mods: list[tuple[str, str | None]] = []

    def add_file(self, origin: str, path: str, raw: bytes) -> None:
        try:
            self.files.setdefault((origin, path), GameFile(origin, path, raw.decode("utf-8-sig")))
        except UnicodeDecodeError:
            log.debug("fichier non UTF-8 ignoré : %s", path)

    def add_mod(self, z: zipfile.ZipFile, mod: str) -> None:
        meta = _load_json(z, "fabric.mod.json") if "fabric.mod.json" in z.namelist() else None
        version = meta.get("version") if isinstance(meta, dict) else None
        self.mods.append((mod, version if isinstance(version, str) else None))
        if meta is not None:
            self.add_file(mod, "fabric.mod.json", z.read("fabric.mod.json"))

    def add_name(self, key: str, value: Any, lang: str, mod: str) -> None:
        match = _LANG_KEY.match(key)
        if not match or not isinstance(value, str):
            return
        kind, namespace, path = match.groups()
        owner = "minecraft" if namespace == "minecraft" else mod
        entry = self.names.setdefault((f"{namespace}:{path}", kind), {"mod": owner, "en": None, "fr": None})
        # Premier arrivé gagne : vanilla est lu avant les mods, qui ne peuvent pas écraser ses noms.
        if entry[lang] is None:
            entry[lang] = value

    def items(self) -> list[Item]:
        return [Item(item_id, e["mod"], kind, e["en"], e["fr"]) for (item_id, kind), e in sorted(self.names.items())]


def _load_json(z: zipfile.ZipFile, name: str) -> Any:
    try:
        return json.loads(z.read(name).decode("utf-8-sig"))
    except (json.JSONDecodeError, UnicodeDecodeError, KeyError):
        log.debug("JSON illisible ignoré : %s", name)
        return None


def _mod_id(z: zipfile.ZipFile, fallback: str) -> str:
    if "fabric.mod.json" in z.namelist():
        meta = _load_json(z, "fabric.mod.json")
        if isinstance(meta, dict) and isinstance(meta.get("id"), str):
            return meta["id"]
    return fallback


def _result(data: dict) -> str | None:
    result = data.get("result", data.get("output"))
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        value = result.get("id", result.get("item"))
        return value if isinstance(value, str) else None
    return None


def _ingredients(value: Any, found: set[str]) -> None:
    if isinstance(value, list):
        for v in value:
            _ingredients(v, found)
    elif isinstance(value, dict):
        if isinstance(value.get("item"), str):
            found.add(value["item"])
        elif isinstance(value.get("tag"), str):
            found.add(f"#{value['tag']}")
        else:
            for v in value.values():
                if isinstance(v, (dict, list)):
                    _ingredients(v, found)


def _scan(z: zipfile.ZipFile, mod: str, out: _Collector, depth: int = 0) -> None:
    for info in z.infolist():
        name = info.filename
        if _DATA_TEXT.match(name) and info.file_size <= MAX_FILE_BYTES:
            out.add_file(mod, name, z.read(name))
        if lang := _LANG_FILE.match(name):
            data = _load_json(z, name)
            if isinstance(data, dict):
                for key, value in data.items():
                    out.add_name(key, value, _LANG_FIELD[lang.group(1)], mod)
        elif recipe := _RECIPE_FILE.match(name):
            data = _load_json(z, name)
            if not isinstance(data, dict) or not isinstance(data.get("type"), str):
                continue
            namespace, path = recipe.groups()
            inputs: set[str] = set()
            for key in _INGREDIENT_KEYS:
                _ingredients(data.get(key), inputs)
            recipe_id = f"{namespace}:{path}"
            out.recipes.setdefault(
                recipe_id,
                Recipe(
                    recipe_id,
                    "minecraft" if namespace == "minecraft" else mod,
                    data["type"],
                    _result(data),
                    sorted(inputs),
                    json.dumps(data, ensure_ascii=False, separators=(",", ":")),
                ),
            )
        elif depth < 2 and _NESTED_JAR.match(name):
            with zipfile.ZipFile(io.BytesIO(z.read(name))) as nested:
                _scan(nested, _mod_id(nested, Path(name).stem), out, depth + 1)


def extract(
    jars: Iterable[Path], vanilla_jar: Path | None, vanilla_lang_fr: dict | None
) -> tuple[list[Item], list[Recipe]]:
    data = extract_all(jars, vanilla_jar, vanilla_lang_fr)
    return data.items, data.recipes


def extract_all(jars: Iterable[Path], vanilla_jar: Path | None, vanilla_lang_fr: dict | None) -> Extracted:
    out = _Collector()
    if vanilla_jar is not None:
        with zipfile.ZipFile(vanilla_jar) as bundler:
            inner = next((n for n in bundler.namelist() if _VANILLA_INNER.match(n)), None)
            if inner is None:
                _scan(bundler, "minecraft", out)
            else:
                with zipfile.ZipFile(io.BytesIO(bundler.read(inner))) as server:
                    _scan(server, "minecraft", out)
        # Le jar serveur n'a que en_us : le français vient des assets Mojang.
        for key, value in (vanilla_lang_fr or {}).items():
            out.add_name(key, value, "fr", "minecraft")
    for jar in sorted(jars):
        try:
            with zipfile.ZipFile(jar) as z:
                mod = _mod_id(z, jar.stem)
                out.add_mod(z, mod)
                _scan(z, mod, out)
        except zipfile.BadZipFile:
            log.warning("jar illisible ignoré : %s", jar.name)
    return Extracted(
        out.items(),
        sorted(out.recipes.values(), key=lambda r: r.id),
        sorted(out.files.values(), key=lambda f: (f.path, f.origin)),
        sorted(out.mods),
    )


def config_files(config_dir: Path) -> list[GameFile]:
    """Configs texte du serveur (`config/...`), origine `config`. Fichier caché, binaire, énorme ou à secret : exclu."""
    files = []
    for path in sorted(config_dir.rglob("*")):
        rel = path.relative_to(config_dir)
        if (
            not path.is_file()
            or path.suffix.lower() not in _CONFIG_SUFFIXES
            or any(part.startswith(".") for part in rel.parts)
            or _SECRET_NAME.search(path.name)
            or path.stat().st_size > MAX_FILE_BYTES
        ):
            continue
        try:
            content = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            continue
        if _SECRET_KEY.search(content):
            log.info("config ignorée (clé de secret) : %s", rel)
            continue
        files.append(GameFile("config", f"config/{rel.as_posix()}", content))
    return files


def fetch_vanilla_lang(version: str, lang: str, client: httpx.Client) -> dict:
    """Langue vanilla via l'index d'assets Mojang (piston-meta → assetIndex → resources)."""
    manifest = client.get("https://piston-meta.mojang.com/mc/game/version_manifest_v2.json").json()
    version_url = next(v["url"] for v in manifest["versions"] if v["id"] == version)
    index_url = client.get(version_url).json()["assetIndex"]["url"]
    digest = client.get(index_url).json()["objects"][f"minecraft/lang/{lang}.json"]["hash"]
    response = client.get(f"https://resources.download.minecraft.net/{digest[:2]}/{digest}")
    response.raise_for_status()
    return response.json()
