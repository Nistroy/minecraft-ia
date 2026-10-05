package io.github.nistroy.minecraftia.cli;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.google.gson.JsonParser;
import java.util.List;
import java.util.Optional;
import org.junit.jupiter.api.Test;

class AgyConfigTest {
    @Test
    void defaultsAreSafe() {
        assertEquals(Optional.empty(), AgyConfig.refusal(""));
        assertEquals(Optional.empty(), AgyConfig.refusal("{\"colorScheme\":\"dark\"}"));
        assertEquals(Optional.empty(), AgyConfig.refusal("{\"toolPermission\":\"strict\","
                + "\"permissions\":{\"allow\":[\"mcp(minecraft-ia/*)\",\"read_url(modrinth.com)\"]}}"));
    }

    @Test
    void autoApprovingModesAndRiskyAllowRulesAreRefused() {
        for (String mode : List.of("always-proceed", "proceed-in-sandbox", "agent-decides", "inconnu")) {
            assertTrue(AgyConfig.refusal("{\"toolPermission\":\"" + mode + "\"}").orElseThrow().contains(mode));
        }
        for (String rule : List.of("command(ls)", "write_file(src/)", "read_file(*)", "unsandboxed(git)", "execute_url(*)")) {
            assertTrue(AgyConfig.refusal("{\"permissions\":{\"allow\":[\"" + rule + "\"]}}").orElseThrow().contains(rule));
        }
        assertTrue(AgyConfig.refusal("{pas du json").isPresent());
    }

    @Test
    void allowMcpAddsRuleOnceAndKeepsOtherSettings() {
        String once = AgyConfig.withMcpAllowed("{\"colorScheme\":\"dark\",\"permissions\":{\"deny\":[\"command(sudo)\"]}}");
        String twice = AgyConfig.withMcpAllowed(once);
        var json = JsonParser.parseString(twice).getAsJsonObject();
        assertEquals("dark", json.get("colorScheme").getAsString());
        assertEquals(1, json.getAsJsonObject("permissions").getAsJsonArray("allow").size());
        assertEquals("mcp(minecraft-ia/*)", json.getAsJsonObject("permissions").getAsJsonArray("allow").get(0).getAsString());
        assertEquals("command(sudo)", json.getAsJsonObject("permissions").getAsJsonArray("deny").get(0).getAsString());
        assertTrue(AgyConfig.withMcpAllowed("").contains("mcp(minecraft-ia/*)"));
    }

    @Test
    void mcpAddArgsPutFlagsBeforeName() {
        McpLink link = new McpLink("https://mc.example.ts.net/mcp", "b".repeat(43));
        assertEquals(List.of("mcp", "add", "--header", "Authorization: Bearer " + link.token(), "minecraft-ia", link.url()),
                AgyConfig.mcpAddArgs(link));
    }
}
