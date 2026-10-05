package io.github.nistroy.minecraftia.cli;

import com.google.gson.JsonObject;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import java.util.Optional;

/**
 * Ligne de commande verrouillée de chaque CLI : seul le MCP du serveur est utilisable, aucun outil sur le PC du joueur
 * (shell, fichiers, web). Le jeton passe par un fichier ou une variable d'environnement, jamais en argument.
 */
public final class CliCommand {
    static final String SERVER = "minecraft-ia";
    static final String TOKEN_ENV = "MINECRAFT_IA_TOKEN";

    /** args = après l'exécutable ; files = fichiers à écrire dans le dossier de travail avant le lancement. */
    public record Invocation(List<String> args, Map<String, String> env, Optional<String> stdin, Map<String, String> files,
            Optional<String> outputFile) {
    }

    private CliCommand() {
    }

    static String prompt(String question) {
        return "Tu es l'assistant du serveur Minecraft moddé (Fabric 1.21.1) d'un groupe de potes. Un joueur te pose "
                + "une question depuis le jeu. Cherche uniquement avec les outils du serveur MCP minecraft-ia (fichiers du "
                + "jeu, tables de loot, configs, fiches des mods, recettes, statut du serveur). Ne devine jamais : si rien "
                + "n'est trouvé, dis-le. Réponds en français, en texte brut court sans Markdown ni tableau (1200 caractères "
                + "max), puis une ligne « Sources : » avec les `source` utilisées.\n\nQuestion du joueur : " + question;
    }

    public static Invocation build(CliKind kind, String question, McpLink link, Path workDir, int timeoutSeconds) {
        return switch (kind) {
            case CLAUDE -> {
                JsonObject server = new JsonObject();
                server.addProperty("type", "http");
                server.addProperty("url", link.url());
                JsonObject headers = new JsonObject();
                headers.addProperty("Authorization", "Bearer " + link.token());
                server.add("headers", headers);
                JsonObject servers = new JsonObject();
                servers.add(SERVER, server);
                JsonObject config = new JsonObject();
                config.add("mcpServers", servers);
                yield new Invocation(List.of("-p", "--output-format", "json", "--no-session-persistence",
                        "--strict-mcp-config", "--mcp-config", workDir.resolve("mcp.json").toString(), "--tools", "",
                        "--allowedTools", "mcp__" + SERVER), Map.of(), Optional.of(prompt(question)),
                        Map.of("mcp.json", config.toString()), Optional.empty());
            }
            // Valeurs `-c` sans guillemets : TOML invalide → lu comme texte brut par Codex, rien à échapper pour cmd.exe.
            case CODEX -> new Invocation(List.of("exec", "--ignore-user-config", "--ephemeral", "--skip-git-repo-check",
                    "-C", workDir.toString(), "-s", "read-only", "-a", "never", "--disable", "shell_tool", "--disable",
                    "unified_exec", "-c", "web_search=disabled", "-c", "tools.view_image=false",
                    "-c", "mcp_servers." + SERVER + ".url=" + link.url(),
                    "-c", "mcp_servers." + SERVER + ".bearer_token_env_var=" + TOKEN_ENV,
                    "-o", workDir.resolve("answer.txt").toString(), "-"),
                    Map.of(TOKEN_ENV, link.token()), Optional.of(prompt(question)), Map.of(), Optional.of("answer.txt"));
            // agy ne lit pas stdin : question en argument, sur une ligne, sans caractère que cmd.exe ou le découpage
            // Windows des arguments interpréterait. MCP et permission : config globale (AgyConfig), après accord du joueur.
            case ANTIGRAVITY -> new Invocation(List.of("--output-format", "json", "--print-timeout", timeoutSeconds + "s",
                    "-p=" + prompt(question).replaceAll("[\"&|<>^%!\\\\\\r\\n]", " ")),
                    Map.of(), Optional.empty(), Map.of(), Optional.empty());
        };
    }
}
