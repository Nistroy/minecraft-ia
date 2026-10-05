package io.github.nistroy.minecraftia.cli;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import java.nio.file.Path;
import org.junit.jupiter.api.Test;

class CliCommandTest {
    private static final McpLink LINK = new McpLink("https://mc.example.ts.net/mcp", "a".repeat(43));
    private static final Path WORK = Path.of("/tmp/minecraft-ia-1");

    @Test
    void claudeHasNoBuiltinToolsAndOnlyOurMcp() {
        CliCommand.Invocation inv = CliCommand.build(CliKind.CLAUDE, "taux de drop du zombie ?", LINK, WORK, 120);
        assertEquals(java.util.List.of("-p", "--output-format", "json", "--no-session-persistence", "--strict-mcp-config",
                "--mcp-config", WORK.resolve("mcp.json").toString(), "--tools", "", "--allowedTools", "mcp__minecraft-ia"),
                inv.args());
        JsonObject server = JsonParser.parseString(inv.files().get("mcp.json")).getAsJsonObject()
                .getAsJsonObject("mcpServers").getAsJsonObject("minecraft-ia");
        assertEquals("http", server.get("type").getAsString());
        assertEquals(LINK.url(), server.get("url").getAsString());
        assertEquals("Bearer " + LINK.token(), server.getAsJsonObject("headers").get("Authorization").getAsString());
        assertTrue(inv.stdin().orElseThrow().endsWith("taux de drop du zombie ?"));
        assertFalse(String.join(" ", inv.args()).contains(LINK.token()));
    }

    @Test
    void codexIsReadOnlyWithoutShellAndTokenOnlyInEnv() {
        CliCommand.Invocation inv = CliCommand.build(CliKind.CODEX, "q", LINK, WORK, 120);
        String args = String.join(" ", inv.args());
        for (String expected : new String[] {"exec", "--ignore-user-config", "--ephemeral", "-s read-only", "-a never",
                "--disable shell_tool", "--disable unified_exec", "-c web_search=disabled", "-c tools.view_image=false",
                "-c mcp_servers.minecraft-ia.url=" + LINK.url(),
                "-c mcp_servers.minecraft-ia.bearer_token_env_var=MINECRAFT_IA_TOKEN", "-C " + WORK}) {
            assertTrue(args.contains(expected), expected);
        }
        assertEquals("-", inv.args().get(inv.args().size() - 1));
        assertEquals(LINK.token(), inv.env().get("MINECRAFT_IA_TOKEN"));
        assertFalse(args.contains(LINK.token()));
        assertEquals("answer.txt", inv.outputFile().orElseThrow());
    }

    @Test
    void antigravityGetsSingleLineSanitizedPromptAsArgument() {
        CliCommand.Invocation inv = CliCommand.build(CliKind.ANTIGRAVITY, "le \"drop\" & 100% ^ ok\\", LINK, WORK, 90);
        assertEquals("--output-format", inv.args().get(0));
        assertTrue(inv.args().contains("--print-timeout") && inv.args().contains("90s"));
        String prompt = inv.args().get(inv.args().size() - 1);
        assertTrue(prompt.startsWith("-p="));
        assertTrue(Executables.safeArgs(Path.of("C:/x/agy.cmd"), inv.args()), prompt);
        assertFalse(prompt.contains("\\"));
        assertTrue(inv.stdin().isEmpty());
    }

    @Test
    void rejectsUnexpectedLinkShapes() {
        assertThrows(IllegalArgumentException.class, () -> new McpLink("http://mc.example.ts.net/mcp", LINK.token()));
        assertThrows(IllegalArgumentException.class, () -> new McpLink("https://x.ts.net/mcp&calc", LINK.token()));
        assertThrows(IllegalArgumentException.class, () -> new McpLink(LINK.url(), "court"));
        assertThrows(IllegalArgumentException.class, () -> new McpLink(LINK.url(), "a".repeat(40) + "&b"));
    }
}
