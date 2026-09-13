package io.github.nistroy.minecraftia;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.net.URI;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class ModConfigTest {
    @TempDir
    Path dir;

    private final Path home = Path.of("/home/test");

    @Test
    void writesDefaultsWhenMissing() throws IOException {
        Path file = dir.resolve("minecraft_ia.json");
        ModConfig config = ModConfig.load(file, home);
        assertEquals(URI.create("http://127.0.0.1:8765"), config.brainUrl());
        assertEquals(home.resolve(".config/minecraft-ia/brain-token"), config.tokenFile());
        assertEquals(256, config.maxQuestionLength());
        assertEquals(Duration.ofSeconds(90), config.timeout());
        assertTrue(Files.exists(file));
        assertEquals(config, ModConfig.load(file, home));
    }

    @Test
    void readsValues() throws IOException {
        Path file = write("""
                {"brainUrl": "http://localhost:9000", "tokenFile": "~/tok", "maxQuestionLength": 100,
                 "timeoutSeconds": 30}""");
        ModConfig config = ModConfig.load(file, home);
        assertEquals(URI.create("http://localhost:9000"), config.brainUrl());
        assertEquals(home.resolve("tok"), config.tokenFile());
        assertEquals(100, config.maxQuestionLength());
        assertEquals(Duration.ofSeconds(30), config.timeout());
    }

    @Test
    void refusesRemoteBrainAndBadNumbers() throws IOException {
        Path remote = write("{\"brainUrl\": \"http://example.com:8765\"}");
        assertThrows(IllegalArgumentException.class, () -> ModConfig.load(remote, home));
        Path zero = write("{\"maxQuestionLength\": 0}");
        assertThrows(IllegalArgumentException.class, () -> ModConfig.load(zero, home));
        Path broken = write("{pas du json");
        assertThrows(IllegalArgumentException.class, () -> ModConfig.load(broken, home));
    }

    private Path write(String json) throws IOException {
        Path file = Files.createTempFile(dir, "config", ".json");
        Files.writeString(file, json);
        return file;
    }
}
