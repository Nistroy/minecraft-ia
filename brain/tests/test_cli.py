import zipfile

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
