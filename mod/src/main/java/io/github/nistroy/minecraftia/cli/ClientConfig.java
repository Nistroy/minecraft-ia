package io.github.nistroy.minecraftia.cli;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonParseException;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Optional;

/** Config du joueur (config/minecraft_ia-client.json) : CLI choisie, chemins, lien MCP reçu du serveur. */
public final class ClientConfig {
    private static final Gson GSON = new GsonBuilder().setPrettyPrinting().create();

    /** Format JSON du fichier ; valeurs = défauts. mode : auto, claude, codex, agy, server (Gemini du serveur). */
    static final class Raw {
        String mode = "auto";
        String claudePath = "";
        String codexPath = "";
        String agyPath = "";
        int timeoutSeconds = 180;
        String mcpUrl = "";
        String mcpToken = "";
        boolean agyConfigured;
    }

    private final Path file;
    private final Raw raw;

    private ClientConfig(Path file, Raw raw) {
        this.file = file;
        this.raw = raw;
    }

    public static ClientConfig load(Path file) throws IOException {
        Raw raw = null;
        if (Files.exists(file)) {
            try {
                raw = GSON.fromJson(Files.readString(file), Raw.class);
            } catch (JsonParseException e) {
                raw = null; // fichier abîmé : défauts, réécrits à la prochaine sauvegarde
            }
        }
        ClientConfig config = new ClientConfig(file, raw == null ? new Raw() : raw);
        if (!Files.exists(file)) {
            config.save();
        }
        return config;
    }

    /** Défauts en mémoire, quand le fichier ne peut pas être lu ni créé. */
    public static ClientConfig defaults(Path file) {
        return new ClientConfig(file, new Raw());
    }

    public void save() throws IOException {
        Files.createDirectories(file.toAbsolutePath().getParent());
        Files.writeString(file, GSON.toJson(raw));
    }

    public String mode() {
        return raw.mode == null ? "auto" : raw.mode;
    }

    public void setMode(String mode) {
        raw.mode = mode;
    }

    public String path(CliKind kind) {
        String value = switch (kind) {
            case CLAUDE -> raw.claudePath;
            case CODEX -> raw.codexPath;
            case ANTIGRAVITY -> raw.agyPath;
        };
        return value == null ? "" : value;
    }

    public int timeoutSeconds() {
        return Math.clamp(raw.timeoutSeconds, 30, 900);
    }

    public Optional<McpLink> link() {
        try {
            return Optional.of(new McpLink(raw.mcpUrl, raw.mcpToken));
        } catch (IllegalArgumentException e) {
            return Optional.empty();
        }
    }

    /** Nouveau lien (ou aucun) : Antigravity doit être reconfiguré avec le nouveau jeton. */
    public void setLink(McpLink link) {
        raw.mcpUrl = link == null ? "" : link.url();
        raw.mcpToken = link == null ? "" : link.token();
        raw.agyConfigured = false;
    }

    public boolean agyConfigured() {
        return raw.agyConfigured;
    }

    public void setAgyConfigured(boolean configured) {
        raw.agyConfigured = configured;
    }
}
