package io.github.nistroy.minecraftia;

import static org.junit.jupiter.api.Assertions.assertEquals;

import org.junit.jupiter.api.Test;

class SourceLabelTest {
    @Test
    void knowledgeBaseSources() {
        assertEquals(new SourceLabel("fiche aether", null), SourceLabel.of("kb:mods/aether.md"));
        assertEquals(new SourceLabel("note aether", null),
                SourceLabel.of("note:notes/aether/2026-09-12-0123abcd.md"));
    }

    @Test
    void exactDataSources() {
        assertEquals(new SourceLabel("recette aether:tools/zanite_pickaxe", null),
                SourceLabel.of("data:recipe:aether:tools/zanite_pickaxe"));
        assertEquals(new SourceLabel("données minecraft:crafting_table", null),
                SourceLabel.of("data:item:minecraft:crafting_table"));
    }

    @Test
    void onlyHttpsUrlsAreLinks() {
        assertEquals(new SourceLabel("modrinth.com/mod/aether", "https://modrinth.com/mod/aether"),
                SourceLabel.of("https://modrinth.com/mod/aether"));
        assertEquals(new SourceLabel("http://example.com", null), SourceLabel.of("http://example.com"));
        assertEquals(new SourceLabel("autre", null), SourceLabel.of("autre"));
    }
}
