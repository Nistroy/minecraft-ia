package io.github.nistroy.minecraftia;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonParseException;
import io.github.nistroy.minecraftia.net.AskPayload;
import java.io.IOException;
import java.net.URI;
import java.net.URISyntaxException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.Set;

/** Config du mod serveur (config/minecraft_ia.json). Créée avec les défauts au premier lancement. */
public record ModConfig(URI brainUrl, Path tokenFile, int maxQuestionLength, Duration timeout) {
    private static final Set<String> LOOPBACK = Set.of("127.0.0.1", "localhost", "[::1]");
    private static final Gson GSON = new GsonBuilder().setPrettyPrinting().create();

    /** Format JSON du fichier ; valeurs = défauts. */
    static final class Raw {
        String brainUrl = "http://127.0.0.1:8765";
        String tokenFile = "~/.config/minecraft-ia/brain-token";
        int maxQuestionLength = 256;
        int timeoutSeconds = 90;
    }

    public static ModConfig load(Path file, Path home) throws IOException {
        Raw raw;
        if (Files.exists(file)) {
            try {
                raw = GSON.fromJson(Files.readString(file), Raw.class);
            } catch (JsonParseException e) {
                throw new IllegalArgumentException("config illisible : " + file, e);
            }
            if (raw == null) {
                raw = new Raw();
            }
        } else {
            raw = new Raw();
            Files.createDirectories(file.toAbsolutePath().getParent());
            Files.writeString(file, GSON.toJson(raw));
        }
        return validate(raw, home);
    }

    private static ModConfig validate(Raw raw, Path home) {
        URI url;
        try {
            url = new URI(raw.brainUrl);
        } catch (URISyntaxException | NullPointerException e) {
            throw new IllegalArgumentException("brainUrl invalide", e);
        }
        // Le jeton ne quitte jamais la machine : cerveau local seulement, jamais via le tunnel.
        if (!"http".equals(url.getScheme()) || url.getHost() == null || !LOOPBACK.contains(url.getHost())) {
            throw new IllegalArgumentException("brainUrl doit être local (http://127.0.0.1:port)");
        }
        if (raw.maxQuestionLength <= 0 || raw.maxQuestionLength > AskPayload.MAX_LENGTH) {
            throw new IllegalArgumentException("maxQuestionLength doit être entre 1 et " + AskPayload.MAX_LENGTH);
        }
        if (raw.timeoutSeconds <= 0) {
            throw new IllegalArgumentException("timeoutSeconds doit être > 0");
        }
        if (raw.tokenFile == null || raw.tokenFile.isBlank()) {
            throw new IllegalArgumentException("tokenFile manquant");
        }
        Path token = raw.tokenFile.startsWith("~/") ? home.resolve(raw.tokenFile.substring(2)) : Path.of(raw.tokenFile);
        return new ModConfig(url, token, raw.maxQuestionLength, Duration.ofSeconds(raw.timeoutSeconds));
    }
}
