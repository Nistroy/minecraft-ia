"""Serveur MCP (Streamable HTTP, 127.0.0.1) : les outils de la `Toolbox` en lecture seule, pour l'IA de chaque joueur
(Claude, ChatGPT, Antigravity…). Aucun LLM ici : c'est l'IA du joueur qui cherche et répond.

Pas de `save_note` ni `answer` : rien n'est écrit depuis l'extérieur. Exposé sur internet par un tunnel HTTPS
(Tailscale Funnel) : seul `/<jeton>/mcp` d'un lien valide répond, tout le reste = 404. Pas de journal d'accès
(le jeton est dans le chemin).
"""

from __future__ import annotations

import json
import logging
from importlib.metadata import version

import uvicorn
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from .config import LOOPBACK
from .llm import ToolCall
from .mcp_links import LinkStore
from .tools import MCP_SPECS, SPECS, Toolbox, ToolContext

MCP_TOOLS = (
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
)
log = logging.getLogger(__name__)
_WEB_TOOLS = frozenset({"modrinth_project", "github_readme", "github_issues"})

INSTRUCTIONS = """\
Serveur Minecraft moddé entre potes (Fabric 1.21.1). Ces outils lisent ce qui est vraiment installé sur le serveur.
- Taux de drop, loot de coffre, spawn, génération, tags : search_files puis read_file (tables de loot dans
  data/<ns>/loot_table/..., configs des mods dans config/...). Recettes et noms FR/EN : find_item, item_recipes.
- Mécaniques et conseils : search_knowledge puis read_fiche ; web en dernier (modrinth_project, github_*).
- Priorité : fichiers du jeu et données exactes > fiches > web. Une config du serveur peut changer une valeur
  par défaut du mod : la vérifier.
- Plusieurs mods peuvent fournir le même fichier (surcharge de datapack) : le dire au joueur.
- Citer les `source` utilisées. Rien trouvé : le dire, ne pas deviner.
"""


def build_mcp(toolbox: Toolbox) -> MCPServer:
    server = MCPServer("minecraft-ia", instructions=INSTRUCTIONS, version=version("minecraft-ia"))
    descriptions = {spec.name: spec.description for spec in (*SPECS, *MCP_SPECS)}

    def call(tool: str, **args: object) -> dict:
        result = toolbox.run(ToolCall(tool, args), ToolContext())
        if "error" in result:
            raise ToolError(json.dumps(result, ensure_ascii=False))
        return result

    def search_knowledge(query: str) -> dict:
        return call("search_knowledge", query=query)

    def read_fiche(slug: str) -> dict:
        return call("read_fiche", slug=slug)

    def find_item(name: str) -> dict:
        return call("find_item", name=name)

    def item_recipes(item_id: str, direction: str = "produce") -> dict:
        return call("item_recipes", item_id=item_id, direction=direction)

    def modrinth_project(slug: str) -> dict:
        return call("modrinth_project", slug=slug)

    def github_readme(repo: str) -> dict:
        return call("github_readme", repo=repo)

    def github_issues(repo: str, query: str) -> dict:
        return call("github_issues", repo=repo, query=query)

    def search_files(query: str, path_filter: str = "") -> dict:
        return call("search_files", query=query, path_filter=path_filter)

    def list_files(prefix: str = "") -> dict:
        return call("list_files", prefix=prefix)

    def read_file(path: str, origin: str = "", offset: int = 0) -> dict:
        return call("read_file", path=path, origin=origin, offset=offset)

    def server_status() -> dict:
        return call("server_status")

    for fn in (
        search_knowledge,
        read_fiche,
        find_item,
        item_recipes,
        modrinth_project,
        github_readme,
        github_issues,
        search_files,
        list_files,
        read_file,
        server_status,
    ):
        server.add_tool(
            fn,
            description=descriptions[fn.__name__],
            annotations=ToolAnnotations(read_only_hint=True, open_world_hint=fn.__name__ in _WEB_TOOLS),
            structured_output=False,
        )
    return server


class SecretPathAuth:
    """`/<jeton>/mcp` d'un lien valide → app MCP sur `/mcp` ; tout le reste → 404, sans dire pourquoi."""

    def __init__(self, app: ASGIApp, links: LinkStore) -> None:
        self._app = app
        self._links = links

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "lifespan":
            await self._app(scope, receive, send)
            return
        if scope["type"] != "http":
            await send({"type": "websocket.close", "code": 1008})
            return
        parts = scope["path"].split("/")
        name = self._links.match(parts[1]) if len(parts) == 3 and parts[2] == "mcp" else None
        if name is None:
            await PlainTextResponse("not found", status_code=404)(scope, receive, send)
            return
        log.info("appel MCP : %s", name)
        await self._app({**scope, "path": "/mcp", "raw_path": b"/mcp"}, receive, send)


def build_app(server: MCPServer, links: LinkStore, public_host: str | None) -> ASGIApp:
    # Protection DNS rebinding du SDK : en-tête Host local ou nom public du tunnel seulement.
    hosts = ["127.0.0.1:*", "localhost:*", "[::1]:*"]
    origins = ["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"]
    if public_host:
        hosts.append(public_host)
        origins.append(f"https://{public_host}")
    security = TransportSecuritySettings(allowed_hosts=hosts, allowed_origins=origins)
    app = server.streamable_http_app(stateless_http=True, json_response=True, transport_security=security)
    return SecretPathAuth(app, links)


def serve_mcp(app: ASGIApp, host: str, port: int) -> None:
    if host not in LOOPBACK:
        raise ValueError(f"le MCP n'écoute qu'en local, pas sur {host!r} : l'exposition passe par un tunnel")
    uvicorn.run(app, host=host, port=port, access_log=False)
