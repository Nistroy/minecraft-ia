package io.github.nistroy.minecraftia.cli;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Optional;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class ClientConfigTest {
    @TempDir
    Path dir;

    @Test
    void defaultsThenRoundTripLinkAndMode() throws Exception {
        Path file = dir.resolve("minecraft_ia-client.json");
        ClientConfig config = ClientConfig.load(file);
        assertEquals("auto", config.mode());
        assertEquals(Optional.empty(), config.link());
        assertTrue(Files.exists(file));
        McpLink link = new McpLink("https://mc.example.ts.net/mcp", "c".repeat(43));
        config.setLink(link);
        config.setMode("codex");
        config.setAgyConfigured(true);
        config.save();
        ClientConfig again = ClientConfig.load(file);
        assertEquals(Optional.of(link), again.link());
        assertEquals("codex", again.mode());
        assertTrue(again.agyConfigured());
    }

    @Test
    void newLinkResetsAntigravitySetupAndBrokenFileFallsBackToDefaults() throws Exception {
        Path file = dir.resolve("c.json");
        ClientConfig config = ClientConfig.load(file);
        config.setAgyConfigured(true);
        config.setLink(new McpLink("https://mc.example.ts.net/mcp", "d".repeat(43)));
        assertEquals(false, config.agyConfigured());
        Files.writeString(file, "{cassé");
        assertEquals("auto", ClientConfig.load(file).mode());
        Files.writeString(file, "{\"mcpUrl\":\"http://evil/mcp\",\"mcpToken\":\"x\"}");
        assertEquals(Optional.empty(), ClientConfig.load(file).link());
    }
}
