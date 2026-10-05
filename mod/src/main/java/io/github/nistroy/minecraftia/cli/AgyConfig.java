package io.github.nistroy.minecraftia.cli;

import com.google.gson.GsonBuilder;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import java.nio.file.Path;
import java.util.List;
import java.util.Optional;
import java.util.Set;

/**
 * Antigravity n'a pas d'option de verrouillage par lancement : MCP et permission vont dans sa config globale, avec
 * l'accord du joueur. En headless, agy refuse seul toute action à approuver (testé 2026-10-05) ; on refuse donc de le
 * lancer si sa config approuve d'office des commandes, écritures ou lectures.
 */
public final class AgyConfig {
    static final String MCP_RULE = "mcp(" + CliCommand.SERVER + "/*)";
    private static final Set<String> SAFE_MODES = Set.of("request-review", "strict");
    private static final List<String> SAFE_ALLOW_PREFIXES = List.of("mcp(", "read_url(");

    private AgyConfig() {
    }

    public static Path settingsFile(Path home) {
        return home.resolve(".gemini/antigravity-cli/settings.json");
    }

    /** Raison de ne pas lancer agy, ou vide si sa config n'approuve rien de dangereux d'office. */
    public static Optional<String> refusal(String settingsJson) {
        JsonObject settings;
        try {
            settings = parse(settingsJson);
        } catch (RuntimeException e) {
            return Optional.of("config Antigravity illisible (settings.json)");
        }
        JsonElement mode = settings.get("toolPermission");
        if (mode != null && !(mode.isJsonPrimitive() && SAFE_MODES.contains(mode.getAsString()))) {
            return Optional.of("Antigravity approuve des actions tout seul (toolPermission = " + mode.getAsString()
                    + ") : repasse en request-review ou strict");
        }
        for (JsonElement rule : allow(settings)) {
            String text = rule.isJsonPrimitive() ? rule.getAsString() : rule.toString();
            if (SAFE_ALLOW_PREFIXES.stream().noneMatch(text::startsWith)) {
                return Optional.of("Antigravity autorise d'office « " + text + " » : retire cette règle (/permissions)");
            }
        }
        return Optional.empty();
    }

    /** settings.json avec la seule règle `mcp(minecraft-ia/*)` en plus ; le reste intact. */
    public static String withMcpAllowed(String settingsJson) {
        JsonObject settings = parse(settingsJson);
        if (!settings.has("permissions") || !settings.get("permissions").isJsonObject()) {
            settings.add("permissions", new JsonObject());
        }
        JsonObject permissions = settings.getAsJsonObject("permissions");
        if (!permissions.has("allow") || !permissions.get("allow").isJsonArray()) {
            permissions.add("allow", new JsonArray());
        }
        JsonArray allow = permissions.getAsJsonArray("allow");
        boolean present = false;
        for (JsonElement rule : allow) {
            present |= rule.isJsonPrimitive() && MCP_RULE.equals(rule.getAsString());
        }
        if (!present) {
            allow.add(MCP_RULE);
        }
        return new GsonBuilder().setPrettyPrinting().create().toJson(settings);
    }

    /** `agy mcp add` : ajoute ou met à jour le serveur ; options avant le nom (règle de la CLI). */
    public static List<String> mcpAddArgs(McpLink link) {
        return List.of("mcp", "add", "--header", "Authorization: Bearer " + link.token(), CliCommand.SERVER, link.url());
    }

    private static JsonObject parse(String settingsJson) {
        if (settingsJson == null || settingsJson.isBlank()) {
            return new JsonObject();
        }
        return JsonParser.parseString(settingsJson).getAsJsonObject();
    }

    private static JsonArray allow(JsonObject settings) {
        if (settings.get("permissions") instanceof JsonObject permissions && permissions.get("allow") instanceof JsonArray a) {
            return a;
        }
        return new JsonArray();
    }
}
