from minecraft_ia.markers import MAX_MARKERS, keep_markers, marker_ids, resource_ids


def test_marker_ids_in_order():
    text = "4 planches [[#minecraft:planks]] pour un établi [[minecraft:crafting_table]]."
    assert marker_ids(text) == ["#minecraft:planks", "minecraft:crafting_table"]


def test_keep_markers_drops_unallowed_with_leading_space():
    text = "Il te faut 4 planches [[#minecraft:planks]] et du diamant [[minecraft:diamond]]."
    assert keep_markers(text, {"#minecraft:planks"}) == "Il te faut 4 planches [[#minecraft:planks]] et du diamant."


def test_malformed_markers_are_removed():
    assert keep_markers("a [[Minecraft:X]] b [[pas un id]] c [[minecraft:inventé]]", set()) == "a b c"


def test_keep_markers_caps_count():
    ids = [f"minecraft:i{n}" for n in range(MAX_MARKERS + 2)]
    text = " ".join(f"x [[{i}]]" for i in ids)
    assert marker_ids(keep_markers(text, set(ids))) == ids[:MAX_MARKERS]


def test_keep_markers_removes_marker_cut_at_the_end():
    assert keep_markers("un établi [[minecraft:craf", {"minecraft:crafting_table"}) == "un établi"


def test_resource_ids_finds_items_and_tags_in_tool_output():
    found = resource_ids('{"inputs": ["#minecraft:planks"], "result": "minecraft:crafting_table"}')
    assert {"#minecraft:planks", "minecraft:crafting_table"} <= found
