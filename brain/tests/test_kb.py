import pytest

from minecraft_ia.kb import KnowledgeBase, NoteStatus

from .conftest import git


def test_reads_fiches_with_frontmatter(kb_root):
    kb = KnowledgeBase(kb_root)
    fiche = kb.fiche("aether")
    assert fiche.meta["nom"] == "The Aether"
    assert "glowstone" in fiche.body
    assert [f.slug for f in kb.fiches()] == ["aether"]


@pytest.mark.parametrize("slug", ["../etc/passwd", "Aether", "", "a/b"])
def test_rejects_unsafe_slug(kb_root, slug):
    assert KnowledgeBase(kb_root).fiche(slug) is None


def test_invalid_frontmatter_is_skipped_not_fatal(kb_root, caplog):
    (kb_root / "mods" / "broken.md").write_text(
        "---\nslug: broken\ncote: S (client_side: unsupported)\n---\n# Broken\n", encoding="utf-8"
    )
    kb = KnowledgeBase(kb_root)
    assert kb.fiche("broken") is None
    assert [f.slug for f in kb.fiches()] == ["aether"]
    assert [d.slug for d in kb.documents()] == ["aether"]
    assert "broken.md" in caplog.text


def test_add_note_writes_file_and_commits(kb_root):
    kb = KnowledgeBase(kb_root)
    note = kb.add_note(
        "aether",
        "Le portail ne s'allume pas avec un briquet.",
        "https://modrinth.com/mod/aether",
        "1.21.1-1.5.11-fabric",
        today="2026-09-12",
        answer_id=7,
    )
    assert note.path.startswith("notes/aether/2026-09-12-")
    assert note.meta["statut"] == NoteStatus.UNVERIFIED
    assert note.meta["reponse"] == 7
    assert kb.note(note.path).body.strip() == "Le portail ne s'allume pas avec un briquet."
    assert git(kb_root, "status", "--porcelain") == ""
    assert "note" in git(kb_root, "log", "-1", "--format=%s")
    assert git(kb_root, "log", "-1", "--format=%an").strip() == "minecraft-ia"


def test_add_note_rejects_unknown_mod_and_empty_source(kb_root):
    kb = KnowledgeBase(kb_root)
    with pytest.raises(ValueError):
        kb.add_note("../x", "fait", "https://x", "1", today="2026-09-12")
    with pytest.raises(ValueError):
        kb.add_note("aether", "fait", " ", "1", today="2026-09-12")
    general = kb.add_note("_general", "fait général", "https://x", "", today="2026-09-12")
    assert general.path.startswith("notes/_general/")


def test_status_transitions(kb_root):
    kb = KnowledgeBase(kb_root)
    note = kb.add_note("aether", "fait", "https://x", "1", today="2026-09-12")
    assert kb.set_note_status(note.path, NoteStatus.PLAYER_CONFIRMED, "vote ✔")
    assert kb.note(note.path).meta["statut"] == NoteStatus.PLAYER_CONFIRMED
    assert kb.set_note_status(note.path, NoteStatus.CONTESTED, "vote ✘")
    assert kb.note(note.path).meta["statut"] == NoteStatus.CONTESTED


def test_votes_never_override_nistroy_validation(kb_root):
    kb = KnowledgeBase(kb_root)
    note = kb.add_note("aether", "fait", "https://x", "1", today="2026-09-12")
    path = kb_root / note.path
    path.write_text(path.read_text(encoding="utf-8").replace("non-vérifié", "validé-nistroy"), encoding="utf-8")
    assert not kb.set_note_status(note.path, NoteStatus.CONTESTED, "vote ✘")
    assert kb.note(note.path).meta["statut"] == NoteStatus.NISTROY_VALIDATED


def test_documents_cover_fiches_and_notes(kb_root):
    kb = KnowledgeBase(kb_root)
    kb.add_note("aether", "fait appris", "https://x", "1", today="2026-09-12")
    docs = {d.kind: d for d in kb.documents()}
    assert docs["fiche"].slug == "aether"
    assert "non-vérifié" in docs["note"].title
    assert "fait appris" in docs["note"].body


def test_write_index_one_line_per_mod(kb_root):
    kb = KnowledgeBase(kb_root)
    kb.write_index()
    index = (kb_root / "index.md").read_text(encoding="utf-8")
    assert "`aether`" in index and "Dimension du ciel" in index
    assert git(kb_root, "status", "--porcelain") == ""
