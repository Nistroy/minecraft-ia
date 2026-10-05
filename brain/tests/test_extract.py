import io
import json
import zipfile

from minecraft_ia.extract import MAX_FILE_BYTES, config_files, extract, extract_all


def make_jar(path, files):
    with zipfile.ZipFile(path, "w") as z:
        for name, content in files.items():
            z.writestr(name, content if isinstance(content, (bytes, str)) else json.dumps(content))
    return path


def nested_jar(files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        for name, content in files.items():
            z.writestr(name, json.dumps(content))
    return buffer.getvalue()


def test_extracts_names_and_recipes(tmp_path):
    jar = make_jar(
        tmp_path / "aether.jar",
        {
            "fabric.mod.json": {"id": "aether", "name": "The Aether"},
            "assets/aether/lang/en_us.json": {
                "item.aether.zanite_gemstone": "Zanite Gemstone",
                "block.aether.skyroot_planks": "Skyroot Planks",
                "entity.aether.moa": "Moa",
                "gui.aether.menu": "ignored",
                # Sous-clés de traduction (motifs de bannière, infobulles) : pas des items.
                "block.minecraft.banner.border.light_blue": "Light Blue Bordure",
                "item.aether.zanite_sword.desc": "tooltip",
            },
            "assets/aether/lang/fr_fr.json": {"item.aether.zanite_gemstone": "Gemme de zanite"},
            "data/aether/recipe/tools/zanite_pickaxe.json": {
                "type": "minecraft:crafting_shaped",
                "key": {"Z": {"item": "aether:zanite_gemstone"}, "S": {"tag": "c:rods/wooden"}},
                "pattern": ["ZZZ", " S ", " S "],
                "result": {"id": "aether:zanite_pickaxe", "count": 1},
            },
            "data/aether/recipe/skyroot_sticks.json": {
                "type": "minecraft:crafting_shapeless",
                "ingredients": [[{"item": "aether:skyroot_planks"}, {"item": "minecraft:oak_planks"}]],
                "result": "aether:skyroot_stick",
            },
            "META-INF/jars/inner.jar": nested_jar(
                {"fabric.mod.json": {"id": "inner"}, "assets/inner/lang/en_us.json": {"item.inner.thing": "Thing"}}
            ),
        },
    )
    items, recipes = extract([jar], vanilla_jar=None, vanilla_lang_fr=None)
    by_id = {(i.id, i.kind): i for i in items}
    assert by_id[("aether:zanite_gemstone", "item")].name_fr == "Gemme de zanite"
    assert by_id[("aether:skyroot_planks", "block")].mod == "aether"
    assert by_id[("aether:moa", "entity")].name_en == "Moa"
    assert ("inner:thing", "item") in by_id
    assert not any(i.id == "aether:menu" for i in items)
    assert all("." not in i.id for i in items), [i.id for i in items]
    recipe = {r.id: r for r in recipes}
    pick = recipe["aether:tools/zanite_pickaxe"]
    assert pick.result == "aether:zanite_pickaxe" and pick.mod == "aether"
    assert sorted(pick.inputs) == ["#c:rods/wooden", "aether:zanite_gemstone"]
    assert recipe["aether:skyroot_sticks"].result == "aether:skyroot_stick"
    assert sorted(recipe["aether:skyroot_sticks"].inputs) == ["aether:skyroot_planks", "minecraft:oak_planks"]


def test_vanilla_jar_and_french_names(tmp_path):
    inner = nested_jar(
        {
            "assets/minecraft/lang/en_us.json": {"block.minecraft.crafting_table": "Crafting Table"},
            "data/minecraft/recipe/crafting_table.json": {
                "type": "minecraft:crafting_shaped",
                "key": {"#": {"tag": "minecraft:planks"}},
                "pattern": ["##", "##"],
                "result": {"id": "minecraft:crafting_table"},
            },
        }
    )
    bundler = make_jar(tmp_path / "server.jar", {"META-INF/versions/1.21.1/server-1.21.1.jar": inner})
    items, recipes = extract([], vanilla_jar=bundler, vanilla_lang_fr={"block.minecraft.crafting_table": "Établi"})
    [table] = items
    assert (table.mod, table.name_fr) == ("minecraft", "Établi")
    assert recipes[0].inputs == ["#minecraft:planks"]


def test_broken_json_is_skipped(tmp_path):
    jar = make_jar(
        tmp_path / "bad.jar",
        {"fabric.mod.json": "{", "data/x/recipe/a.json": "{nope", "assets/x/lang/en_us.json": {"item.x.a": "A"}},
    )
    items, recipes = extract([jar], vanilla_jar=None, vanilla_lang_fr=None)
    assert [i.mod for i in items] == ["bad"] and recipes == []


def test_collects_data_files_and_top_level_mod_meta(tmp_path):
    jar = make_jar(
        tmp_path / "zombies.jar",
        {
            "fabric.mod.json": {"id": "zombies", "version": "1.2.0"},
            "data/zombies/loot_table/entities/ghoul.json": {"pools": [{"rolls": 1}]},
            "data/zombies/function/tick.mcfunction": "say hi",
            "data/zombies/structure/hut.nbt": b"\x0a\x00",
            "assets/zombies/textures/ghoul.png": b"png",
            "META-INF/jars/lib.jar": nested_jar(
                {"fabric.mod.json": {"id": "lib", "version": "9"}, "data/lib/tags/item/x.json": {"values": []}}
            ),
        },
    )
    data = extract_all([jar], vanilla_jar=None, vanilla_lang_fr=None)
    assert {(f.origin, f.path) for f in data.files} == {
        ("zombies", "fabric.mod.json"),
        ("zombies", "data/zombies/loot_table/entities/ghoul.json"),
        ("zombies", "data/zombies/function/tick.mcfunction"),
        ("lib", "data/lib/tags/item/x.json"),
    }
    assert data.mods == [("zombies", "1.2.0")]
    ghoul = next(f for f in data.files if f.path.endswith("ghoul.json"))
    assert json.loads(ghoul.content) == {"pools": [{"rolls": 1}]}


def test_config_files_skip_secrets_binaries_and_big_files(tmp_path):
    cfg = tmp_path / "config"
    (cfg / "rpg").mkdir(parents=True)
    (cfg / "spark" / "tmp").mkdir(parents=True)
    (cfg / "aether-common.toml").write_text("[drops]\nchance = 0.5\n", encoding="utf-8")
    (cfg / "rpg" / "report.json").write_text('{"minecraft:chests/secret_room": {"name": "Secret Room"}}')
    (cfg / "web.json").write_text('{\n  "password": "x"\n}')
    (cfg / "ia.json").write_text('{"brainUrl": "", "tokenFile": "/x"}')
    (cfg / "bot.properties").write_text("Discord_Token=abc\n")
    (cfg / "server.properties").write_text("rcon.password=abc\n")
    (cfg / "spark" / "tmp" / "profile.jfr.tmp").write_bytes(b"\x00")
    (cfg / "huge.json").write_text("x" * (MAX_FILE_BYTES + 1))
    (cfg / ".hidden.json").write_text("{}")
    files = {f.path: f for f in config_files(cfg)}
    assert set(files) == {"config/aether-common.toml", "config/rpg/report.json"}
    assert files["config/aether-common.toml"].origin == "config"
