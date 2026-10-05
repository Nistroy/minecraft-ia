import json

import anyio
import pytest
from mcp import Client
from starlette.testclient import TestClient

from minecraft_ia.db import GameFile
from minecraft_ia.kb import KnowledgeBase
from minecraft_ia.mcp_links import LinkStore
from minecraft_ia.mcp_server import MCP_TOOLS, build_app, build_mcp, serve_mcp
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


def test_serve_refuses_non_loopback_host():
    with pytest.raises(ValueError):
        serve_mcp(object(), "0.0.0.0", 8766)  # noqa: S104 — refus attendu


PUBLIC = "mc.example.ts.net"
INIT = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}},
}
HEADERS = {"Accept": "application/json, text/event-stream"}


@pytest.fixture
def links(tmp_path):
    return LinkStore(tmp_path / "mcp-links.json")


@pytest.fixture
def http(server, links):
    with TestClient(build_app(server, links, PUBLIC), base_url=f"https://{PUBLIC}") as client:
        yield client


def test_secret_link_reaches_mcp(http, links):
    token = links.add("bob")
    response = http.post(f"/{token}/mcp", json=INIT, headers=HEADERS)
    assert response.status_code == 200 and response.json()["result"]["serverInfo"]["name"] == "minecraft-ia"


@pytest.mark.parametrize("path", ["/mcp", "/mauvais-jeton/mcp", "/", "/{token}/autre", "/{token}"])
def test_anything_but_a_valid_link_is_404(http, links, path):
    token = links.add("bob")
    assert http.post(path.format(token=token), json=INIT, headers=HEADERS).status_code == 404


def test_revoked_link_stops_working_immediately(http, links):
    token = links.add("bob")
    links.revoke("bob")
    assert http.post(f"/{token}/mcp", json=INIT, headers=HEADERS).status_code == 404


def test_unknown_host_is_refused(server, links):
    token = links.add("bob")
    with TestClient(build_app(server, links, PUBLIC), base_url="https://evil.example") as client:
        assert client.post(f"/{token}/mcp", json=INIT, headers=HEADERS).status_code == 421


def test_tool_argument_called_name_reaches_the_toolbox(server):
    # Régression : `find_item(name=...)` entrait en collision avec le paramètre du relais interne.
    result = session(server, lambda c: c.call_tool("find_item", {"name": "zombie"}))
    assert not result.is_error and json.loads(result.content[0].text) == {"items": []}


def test_bearer_header_on_plain_path_reaches_mcp(http, links):
    token = links.add("bob")
    response = http.post("/mcp", json=INIT, headers={**HEADERS, "Authorization": f"Bearer {token}"})
    assert response.status_code == 200


@pytest.mark.parametrize("path, auth", [("/mcp", "Bearer faux"), ("/mcp", "Basic x"), ("/autre", "Bearer {token}")])
def test_bad_bearer_or_path_is_404(http, links, path, auth):
    token = links.add("bob")
    response = http.post(path, json=INIT, headers={**HEADERS, "Authorization": auth.format(token=token)})
    assert response.status_code == 404
