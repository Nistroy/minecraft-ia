"""Marqueurs d'icônes dans les réponses : `[[ns:id]]` (item/bloc) ou `[[#ns:tag]]`, dessinés par l'écran du mod.

Anti-invention : un marqueur n'est gardé que si son id a été renvoyé par un outil pendant la recherche et existe
dans les données extraites des jars (vérifié par l'appelant) ; sinon il disparaît et le mot reste.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

MAX_MARKERS = 6

_ID = r"#?[a-z0-9_.-]+:[a-z0-9_./-]+"
_ID_ONLY = re.compile(rf"^{_ID}$")
_RESOURCE_ID = re.compile(_ID)
# Tout `[[...]]`, valide ou non, avec l'espace qui le précède : un marqueur retiré ne laisse pas de trou.
_MARKER = re.compile(r"\s?\[\[([^\[\]\n]*)\]\]")
# Marqueur coupé par la limite de longueur de réponse.
_CUT = re.compile(r"\s?\[\[[^\]\n]*\]?$")


def resource_ids(text: str) -> set[str]:
    """Ids `ns:id` / `#ns:tag` présents dans un texte (résultat d'outil)."""
    return set(_RESOURCE_ID.findall(text))


def marker_ids(text: str) -> list[str]:
    return [m.group(1) for m in _MARKER.finditer(text) if _ID_ONLY.match(m.group(1))]


def keep_markers(text: str, allowed: Iterable[str]) -> str:
    """Garde les MAX_MARKERS premiers marqueurs autorisés, retire les autres (et les malformés)."""
    allowed = set(allowed)
    kept = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal kept
        marker_id = match.group(1)
        if kept < MAX_MARKERS and marker_id in allowed and _ID_ONLY.match(marker_id):
            kept += 1
            return match.group(0)
        return ""

    return _CUT.sub("", _MARKER.sub(replace, text)).strip()
