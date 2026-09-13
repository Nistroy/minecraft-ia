import pytest

from minecraft_ia.db import Item, KbDoc, Recipe
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
