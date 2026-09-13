import subprocess
from pathlib import Path

import pytest

from minecraft_ia.db import Database

FICHE_AETHER = """---
slug: aether
nom: The Aether
namespaces: [aether]
version: 1.21.1-1.5.11-fabric
cote: S+C
resume: Dimension du ciel, portail en glowstone
sources:
  m: https://modrinth.com/mod/aether
verifie: 2026-09-12
---
# The Aether
## Mécaniques
- Portail : cadre de glowstone, activé avec un seau d'eau [m]
"""


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True).stdout


@pytest.fixture
def db(tmp_path: Path) -> Database:
    database = Database(tmp_path / "brain.sqlite3")
    yield database
    database.close()


@pytest.fixture
def kb_root(tmp_path: Path) -> Path:
    root = tmp_path / "kb"
    (root / "mods").mkdir(parents=True)
    (root / "mods" / "aether.md").write_text(FICHE_AETHER, encoding="utf-8")
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.name", "test")
    git(root, "config", "user.email", "test@example.invalid")
    git(root, "add", ".")
    git(root, "commit", "-q", "-m", "init")
    return root
