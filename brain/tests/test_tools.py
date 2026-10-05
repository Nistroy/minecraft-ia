import pytest

from minecraft_ia.db import GameFile, Item, KbDoc, Recipe
from minecraft_ia.kb import KnowledgeBase
from minecraft_ia.llm import ToolCall
from minecraft_ia.tools import Toolbox, ToolContext


class FakeHttp:
    def __init__(self, routes):
        self.routes = routes
        self.urls = []

    def get_json(self, url, params=None):
        self.urls.append((url, params))
        return self.routes[url]

    def get_text(self, url):
        self.urls.append((url, None))
        return self.routes[url]


@pytest.fixture
def toolbox(db, kb_root):
    kb = KnowledgeBase(kb_root)
    db.replace_kb_index(kb.documents())
    db.replace_exact_data(
        [Item("minecraft:crafting_table", "minecraft", "block", "Crafting Table", "Établi")],
        [
            Recipe(
                "minecraft:crafting_table",
                "minecraft",
                "minecraft:crafting_shaped",
                "minecraft:crafting_table",
                ["#minecraft:planks"],
                '{"pattern": ["##", "##"]}',
            )
        ],
    )
    http = FakeHttp(
        {
            "https://api.modrinth.com/v2/project/aether": {
                "slug": "aether",
                "title": "The Aether",
                "description": "Ciel",
                "body": "x" * 20000,
                "wiki_url": "https://aether.wiki",
                "source_url": "https://github.com/The-Aether-Team/The-Aether",
                "issues_url": None,
            },
            "https://api.github.com/repos/The-Aether-Team/The-Aether/readme": "# README",
            "https://api.github.com/search/issues": {
                "items": [
                    {
                        "title": "Portal bug",
                        "state": "open",
                        "html_url": "https://github.com/The-Aether-Team/The-Aether/issues/1",
                        "body": "b" * 3000,
                    }
                ]
            },
        }
    )
    return Toolbox(db, kb, http), http


def run(box, tool, **args):
    ctx = ToolContext()
    return box.run(ToolCall(tool, args), ctx), ctx


def test_specs_include_answer_tool(toolbox):
    box, _ = toolbox
    names = {s.name for s in box.specs()}
    assert {
        "search_knowledge",
        "read_fiche",
        "find_item",
        "item_recipes",
        "modrinth_project",
        "github_readme",
        "github_issues",
        "save_note",
        "answer",
    } <= names


def test_search_knowledge_registers_sources(toolbox):
    result, ctx = run(toolbox[0], "search_knowledge", query="portail glowstone")
    assert result["results"][0]["source"] == "kb:mods/aether.md"
    assert "kb:mods/aether.md" in ctx.seen


def test_read_fiche_and_unknown_slug(toolbox):
    result, ctx = run(toolbox[0], "read_fiche", slug="aether")
    assert "glowstone" in result["content"] and result["meta"]["version"] == "1.21.1-1.5.11-fabric"
    assert "kb:mods/aether.md" in ctx.seen
    result, ctx = run(toolbox[0], "read_fiche", slug="../../secret")
    assert "error" in result and not ctx.seen


def test_exact_data_tools(toolbox):
    result, ctx = run(toolbox[0], "find_item", name="etabli")
    assert result["items"][0]["id"] == "minecraft:crafting_table"
    assert "data:item:minecraft:crafting_table" in ctx.seen
    result, ctx = run(toolbox[0], "item_recipes", item_id="minecraft:crafting_table", direction="produce")
    assert result["recipes"][0]["inputs"] == ["#minecraft:planks"]
    assert "data:recipe:minecraft:crafting_table" in ctx.seen


def test_tool_results_register_item_ids(toolbox):
    _, ctx = run(toolbox[0], "item_recipes", item_id="minecraft:crafting_table", direction="produce")
    assert {"minecraft:crafting_table", "#minecraft:planks"} <= ctx.item_ids
    _, ctx = run(toolbox[0], "find_item", name="etabli")
    assert "minecraft:crafting_table" in ctx.item_ids


def test_modrinth_truncates_and_uses_installed_version(toolbox):
    box, http = toolbox
    result, ctx = run(box, "modrinth_project", slug="aether")
    assert len(result["body"]) <= 6000
    assert result["installed_version"] == "1.21.1-1.5.11-fabric"
    assert "https://modrinth.com/mod/aether" in ctx.seen


def test_github_tools_validate_repo(toolbox):
    box, http = toolbox
    result, ctx = run(box, "github_readme", repo="The-Aether-Team/The-Aether")
    assert result["content"] == "# README" and "https://github.com/The-Aether-Team/The-Aether" in ctx.seen
    result, ctx = run(box, "github_readme", repo="evil.com/../x?y")
    assert "error" in result
    result, ctx = run(box, "github_issues", repo="The-Aether-Team/The-Aether", query="portal")
    assert http.urls[-1][1]["q"] == "repo:The-Aether-Team/The-Aether is:issue portal"
    assert len(result["issues"][0]["body"]) <= 800
    assert "https://github.com/The-Aether-Team/The-Aether/issues/1" in ctx.seen


def test_save_note_requires_seen_web_source(toolbox):
    box, _ = toolbox
    ctx = ToolContext()
    refused = box.run(ToolCall("save_note", {"mod": "aether", "fact": "f", "source": "https://inventé"}), ctx)
    assert "error" in refused and not ctx.pending_notes
    box.run(ToolCall("modrinth_project", {"slug": "aether"}), ctx)
    ok = box.run(
        ToolCall("save_note", {"mod": "aether", "fact": "f", "source": "https://modrinth.com/mod/aether"}), ctx
    )
    assert ok == {"saved": True} and ctx.pending_notes[0].mod == "aether"


def test_unknown_tool_and_bad_args_are_errors_not_crashes(toolbox):
    box, _ = toolbox
    assert "error" in run(box, "rm_rf")[0]
    assert "error" in run(box, "find_item")[0]


def test_kb_hits_for_notes_carry_note_source(db, kb_root):
    db.replace_kb_index(
        [
            KbDoc(
                "notes/aether/2026-09-12-0123abcd.md",
                "aether",
                "note",
                "note non-vérifié",
                "Le portail craint le briquet",
            )
        ]
    )
    box = Toolbox(db, KnowledgeBase(kb_root), FakeHttp({}))
    result, ctx = run(box, "search_knowledge", query="briquet")
    assert result["results"][0]["source"] == "note:notes/aether/2026-09-12-0123abcd.md"
    assert "note:notes/aether/2026-09-12-0123abcd.md" in ctx.seen


ZOMBIE = "data/minecraft/loot_table/entities/zombie.json"


@pytest.fixture
def filebox(db, kb_root):
    db.replace_game_files(
        [
            GameFile("minecraft", ZOMBIE, '{"item": "minecraft:rotten_flesh"}'),
            GameFile("zombies", ZOMBIE, '{"item": "zombies:brain"}'),
            GameFile("zombies", "data/zombies/loot_table/entities/ghoul.json", "g" * 30000),
            GameFile("zombies", "fabric.mod.json", '{"id": "zombies"}'),
            GameFile("config", "config/zombies.toml", "brain_drop_chance = 0.25"),
        ],
        mods=[("zombies", "1.2.0")],
    )
    status = {"online": True, "version": "1.21.1", "players_online": 1, "players_max": 5, "players": ["Steve"]}
    return Toolbox(db, KnowledgeBase(kb_root), FakeHttp({}), status=lambda: status)


def test_search_files_registers_file_sources(filebox):
    result, ctx = run(filebox, "search_files", query="rotten_flesh")
    assert result["results"] == [
        {
            "source": f"file:minecraft/{ZOMBIE}",
            "origin": "minecraft",
            "path": ZOMBIE,
            "lines": ['{"item": "minecraft:rotten_flesh"}'],
        }
    ]
    assert f"file:minecraft/{ZOMBIE}" in ctx.seen
    assert "error" in run(filebox, "search_files", query="  ")[0]


def test_list_files_groups_by_directory(filebox):
    root, _ = run(filebox, "list_files")
    assert root["dirs"] == {"config/": 1, "data/": 3}
    assert root["files"] == [{"path": "fabric.mod.json", "origins": ["zombies"]}]
    entities, _ = run(filebox, "list_files", prefix="/data/minecraft/loot_table/entities")
    assert entities["dirs"] == {}
    assert entities["files"] == [{"path": ZOMBIE, "origins": ["minecraft", "zombies"]}]
    assert "error" in run(filebox, "list_files", prefix="data/../config")[0]


def test_read_file_pages_and_disambiguates_origins(filebox):
    ambiguous, ctx = run(filebox, "read_file", path=ZOMBIE)
    assert ambiguous["origins"] == ["minecraft", "zombies"] and "error" in ambiguous and not ctx.seen
    result, ctx = run(filebox, "read_file", path=ZOMBIE, origin="zombies")
    assert result["content"] == '{"item": "zombies:brain"}' and result["next_offset"] is None
    assert f"file:zombies/{ZOMBIE}" in ctx.seen
    first, _ = run(filebox, "read_file", path="data/zombies/loot_table/entities/ghoul.json")
    assert len(first["content"]) == 20000 and first["next_offset"] == 20000 and first["total_chars"] == 30000
    second, _ = run(filebox, "read_file", path="data/zombies/loot_table/entities/ghoul.json", offset=20000)
    assert len(second["content"]) == 10000 and second["next_offset"] is None
    assert "error" in run(filebox, "read_file", path="data/nope.json")[0]


def test_server_status_adds_installed_mods(filebox):
    result, ctx = run(filebox, "server_status")
    assert result["online"] is True and result["players"] == ["Steve"]
    assert result["mods"] == [{"id": "zombies", "version": "1.2.0"}]
    assert "live:server" in ctx.seen


def test_server_status_without_provider_is_an_error(db, kb_root):
    box = Toolbox(db, KnowledgeBase(kb_root), FakeHttp({}))
    assert "error" in run(box, "server_status")[0]


def test_gemini_specs_unchanged_by_mcp_only_tools(toolbox):
    names = {s.name for s in toolbox[0].specs()}
    assert not names & {"search_files", "list_files", "read_file", "server_status"}
