import sqlite3

import pytest

from minecraft_ia.db import Database, Item, KbDoc, Recipe

PLAYER = "0f1e2d3c-0000-0000-0000-000000000001"


def test_migrations_are_applied_once(tmp_path):
    path = tmp_path / "b.sqlite3"
    first = Database(path)
    version = first.schema_version()
    first.close()
    second = Database(path)
    assert second.schema_version() == version >= 1
    second.close()


def test_tables_are_strict(db):
    with pytest.raises(sqlite3.IntegrityError):
        db._conn.execute("INSERT INTO llm_usage (day, calls) VALUES ('2026-09-12', 'beaucoup')")


def test_question_answer_history_roundtrip(db):
    qid = db.add_question(PLAYER, "Steve", "comment aller dans l'Aether ?", day="2026-09-12")
    aid = db.add_answer(
        qid, "Cadre de glowstone + eau.", ["kb:mods/aether.md"], "ok", llm_calls=2, notes=["notes/aether/x.md"]
    )
    row = db.answer(aid)
    assert row.player == PLAYER
    assert row.question == "comment aller dans l'Aether ?"
    assert row.sources == ["kb:mods/aether.md"]
    assert row.notes == ["notes/aether/x.md"]
    history = db.history(PLAYER, limit=10)
    assert [h.answer_id for h in history] == [aid]
    assert history[0].vote is None


def test_history_is_private_per_player_and_newest_first(db):
    q1 = db.add_question(PLAYER, "Steve", "q1", day="2026-09-12")
    a1 = db.add_answer(q1, "r1", [], "unknown", llm_calls=1, notes=[])
    q2 = db.add_question(PLAYER, "Steve", "q2", day="2026-09-12")
    a2 = db.add_answer(q2, "r2", [], "unknown", llm_calls=1, notes=[])
    other = db.add_question("other", "Alex", "q3", day="2026-09-12")
    db.add_answer(other, "r3", [], "unknown", llm_calls=1, notes=[])
    assert [h.answer_id for h in db.history(PLAYER, limit=10)] == [a2, a1]


def test_vote_upsert_shows_in_history(db):
    qid = db.add_question(PLAYER, "Steve", "q", day="2026-09-12")
    aid = db.add_answer(qid, "r", [], "ok", llm_calls=1, notes=[])
    db.add_vote(aid, PLAYER, up=True)
    db.add_vote(aid, PLAYER, up=False)
    assert db.history(PLAYER, limit=1)[0].vote is False


def test_daily_counters(db):
    db.add_question(PLAYER, "Steve", "q", day="2026-09-12")
    db.add_question(PLAYER, "Steve", "q", day="2026-09-13")
    assert db.questions_on(PLAYER, "2026-09-12") == 1
    db.add_llm_calls("2026-09-12", 3)
    db.add_llm_calls("2026-09-12", 2)
    assert db.llm_calls_on("2026-09-12") == 5
    assert db.llm_calls_on("2026-09-13") == 0


def test_exact_data_search_and_recipes(db):
    items = [
        Item("minecraft:crafting_table", "minecraft", "block", "Crafting Table", "Établi"),
        Item("aether:skyroot_planks", "aether", "block", "Skyroot Planks", "Planches de bois céleste"),
    ]
    recipes = [
        Recipe(
            "aether:skyroot_table",
            "aether",
            "minecraft:crafting_shaped",
            "minecraft:crafting_table",
            ["aether:skyroot_planks"],
            '{"type": "minecraft:crafting_shaped"}',
        )
    ]
    db.replace_exact_data(items, recipes)
    assert [i.id for i in db.find_items("etabli", limit=5)] == ["minecraft:crafting_table"]
    assert db.item("aether:skyroot_planks").name_fr == "Planches de bois céleste"
    assert [r.id for r in db.recipes_producing("minecraft:crafting_table", limit=5)] == ["aether:skyroot_table"]
    assert [r.id for r in db.recipes_using("aether:skyroot_planks", limit=5)] == ["aether:skyroot_table"]
    db.replace_exact_data([], [])
    assert db.find_items("etabli", limit=5) == []


def test_kb_index_search_tolerates_fts_syntax(db):
    db.replace_kb_index(
        [
            KbDoc("mods/aether.md", "aether", "fiche", "The Aether", "Portail : cadre de glowstone, seau d'eau"),
            KbDoc("mods/tide.md", "tide", "fiche", "Tide", "Pêche, canne à pêche améliorée"),
        ]
    )
    hits = db.search_kb('portail "glowstone" AND (', limit=5)
    assert [h.path for h in hits] == ["mods/aether.md"]
    assert db.search_kb("peche", limit=5)[0].slug == "tide"
    assert db.search_kb("   ", limit=5) == []
