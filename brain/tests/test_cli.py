import zipfile

from minecraft_ia import cli
from minecraft_ia.cli import main
from minecraft_ia.db import Database

from .test_assistant import ScriptedLLM, call


def config(tmp_path, kb_root, **extra):
    lines = [f'kb_path = "{kb_root}"', 'db_path = "brain.sqlite3"', 'token_file = "brain-token"']
    lines += [f'{k} = "{v}"' for k, v in extra.items()]
    path = tmp_path / "config.toml"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_kb_index_writes_index_and_fts(tmp_path, kb_root, capsys):
    cfg = config(tmp_path, kb_root)
    assert main(["--config", str(cfg), "kb", "index"]) == 0
    assert "`aether`" in (kb_root / "index.md").read_text(encoding="utf-8")
    db = Database(tmp_path / "brain.sqlite3")
    assert db.search_kb("glowstone", 5)[0].slug == "aether"
    db.close()


def test_extract_without_network(tmp_path, kb_root, capsys):
    mods = tmp_path / "mods"
    mods.mkdir()
    with zipfile.ZipFile(mods / "x.jar", "w") as z:
        z.writestr("fabric.mod.json", '{"id": "x"}')
        z.writestr("assets/x/lang/en_us.json", '{"item.x.gem": "Gem"}')
    cfg = config(tmp_path, kb_root, mods_dir=mods)
    assert main(["--config", str(cfg), "extract", "--no-vanilla-fr"]) == 0
    assert "1 noms" in capsys.readouterr().out
    db = Database(tmp_path / "brain.sqlite3")
    assert db.item("x:gem").name_en == "Gem"
    db.close()


def test_extract_stores_game_files_and_server_config(tmp_path, kb_root, capsys):
    mods = tmp_path / "mods"
    mods.mkdir()
    with zipfile.ZipFile(mods / "x.jar", "w") as z:
        z.writestr("fabric.mod.json", '{"id": "x", "version": "2.0"}')
        z.writestr("data/x/loot_table/entities/gem_golem.json", '{"pools": []}')
    server_config = tmp_path / "server-config"
    server_config.mkdir()
    (server_config / "x.toml").write_text("drop_chance = 0.5\n", encoding="utf-8")
    cfg = config(tmp_path, kb_root, mods_dir=mods, config_dir=server_config)
    assert main(["--config", str(cfg), "extract", "--no-vanilla-fr"]) == 0
    assert "3 fichiers" in capsys.readouterr().out
    db = Database(tmp_path / "brain.sqlite3")
    assert [f.origin for f in db.game_files("config/x.toml")] == ["config"]
    assert db.installed_mods() == [("x", "2.0")]
    db.close()


def test_mcp_serves_on_configured_local_port_without_gemini_key(tmp_path, kb_root, monkeypatch):
    served = []
    monkeypatch.setattr(cli, "serve_mcp", lambda server, host, port: served.append((server.name, host, port)))
    cfg = config(tmp_path, kb_root)
    with cfg.open("a", encoding="utf-8") as f:
        f.write("mcp_port = 9123\n")

    def no_llm(_cfg):
        raise AssertionError("le MCP n'appelle aucun LLM")

    assert main(["--config", str(cfg), "mcp"], llm_factory=no_llm) == 0
    assert served == [("minecraft-ia", "127.0.0.1", 9123)]


def test_ask_prints_answer_and_sources(tmp_path, kb_root, capsys):
    cfg = config(tmp_path, kb_root)
    main(["--config", str(cfg), "kb", "index"])
    llm = ScriptedLLM(
        call("search_knowledge", query="portail"),
        call("answer", text="Glowstone + eau.", sources=["kb:mods/aether.md"]),
    )
    assert main(["--config", str(cfg), "ask", "portail aether ?"], llm_factory=lambda _cfg: [llm]) == 0
    out = capsys.readouterr().out
    assert "Glowstone + eau." in out and "kb:mods/aether.md" in out


def test_bad_config_exits_with_message(tmp_path, capsys):
    bad = tmp_path / "config.toml"
    bad.write_text('host = "0.0.0.0"\n', encoding="utf-8")
    assert main(["--config", str(bad), "kb", "index"]) == 2
    assert "kb_path" in capsys.readouterr().err
