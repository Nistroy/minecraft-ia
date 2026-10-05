import json

import anyio
import pytest
from mcp import Client

from minecraft_ia.db import GameFile
from minecraft_ia.kb import KnowledgeBase
from minecraft_ia.mcp_server import MCP_TOOLS, build_mcp, serve_mcp
from minecraft_ia.tools import Toolbox

from .test_tools import FakeHttp

ZOMBIE = "data/minecraft/loot_table/entities/zombie.json"


@pytest.fixture
def server(db, kb_root):
    kb = KnowledgeBase(kb_root)
    db.replace_kb_index(kb.documents())
    db.replace_game_files([GameFile("minecraft", ZOMBIE, '{"item": "minecraft:rotten_flesh"}')], mods=[])
    return build_mcp(Toolbox(db, kb, FakeHttp({}), status=lambda: {"online": False}))


def session(server, action):
    async def main():
        async with Client(server) as client:
            return await action(client)

    return anyio.run(main)


def test_exposes_read_only_tools_without_writes_or_answer(server):
    tools = session(server, lambda c: c.list_tools()).tools
    assert (
        {t.name for t in tools}
        == set(MCP_TOOLS)
        == {
            "search_knowledge",
            "read_fiche",
            "find_item",
            "item_recipes",
            "modrinth_project",
            "github_readme",
            "github_issues",
            "search_files",
            "list_files",
            "read_file",
            "server_status",
        }
    )
    assert all(t.annotations.read_only_hint and t.description for t in tools)
    web = {t.name for t in tools if t.annotations.open_world_hint}
    assert web == {"modrinth_project", "github_readme", "github_issues"}


def test_tool_call_returns_json(server):
    result = session(server, lambda c: c.call_tool("search_files", {"query": "rotten_flesh"}))
    assert not result.is_error
    assert json.loads(result.content[0].text)["results"][0]["source"] == f"file:minecraft/{ZOMBIE}"


def test_tool_error_is_flagged_with_its_message(server):
    result = session(server, lambda c: c.call_tool("read_file", {"path": "data/nope.json"}))
    assert result.is_error and "introuvable" in result.content[0].text


def test_instructions_ask_for_sources(server):
    assert "source" in server.instructions


def test_serve_refuses_non_loopback_host(server):
    with pytest.raises(ValueError):
        serve_mcp(server, "0.0.0.0", 8766)  # noqa: S104 — refus attendu


def test_tool_argument_called_name_reaches_the_toolbox(server):
    # Régression : `find_item(name=...)` entrait en collision avec le paramètre du relais interne.
    result = session(server, lambda c: c.call_tool("find_item", {"name": "zombie"}))
    assert not result.is_error and json.loads(result.content[0].text) == {"items": []}
