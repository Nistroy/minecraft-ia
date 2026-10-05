package io.github.nistroy.minecraftia.cli;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.Optional;
import org.junit.jupiter.api.Test;

class CliOutputTest {
    private static CliRunner.Result run(int exit, String out, String err) {
        return new CliRunner.Result(exit, out, err, false);
    }

    @Test
    void claudeJsonResult() {
        CliOutput ok = CliOutput.parse(CliKind.CLAUDE, run(0,
                "{\"type\":\"result\",\"subtype\":\"success\",\"is_error\":false,\"result\":\"1 chair putréfiée\"}", ""), Optional.empty());
        assertTrue(ok.ok());
        assertEquals("1 chair putréfiée", ok.text());
        CliOutput err = CliOutput.parse(CliKind.CLAUDE, run(1,
                "{\"type\":\"result\",\"is_error\":true,\"result\":\"Not logged in\"}", ""), Optional.empty());
        assertFalse(err.ok());
        assertTrue(err.text().contains("Not logged in"));
    }

    @Test
    void codexReadsLastMessageFile() {
        assertEquals("Réponse", CliOutput.parse(CliKind.CODEX, run(0, "", ""), Optional.of("Réponse\n")).text());
        CliOutput err = CliOutput.parse(CliKind.CODEX, run(1, "", "boom\nlogin required"), Optional.empty());
        assertFalse(err.ok());
        assertTrue(err.text().contains("login required"));
    }

    @Test
    void antigravityJson() {
        assertEquals("Oui", CliOutput.parse(CliKind.ANTIGRAVITY,
                run(0, "{\"status\":\"SUCCESS\",\"response\":\"Oui\",\"error\":\"\"}", ""), Optional.empty()).text());
        CliOutput err = CliOutput.parse(CliKind.ANTIGRAVITY,
                run(1, "{\"status\":\"ERROR\",\"response\":\"\",\"error\":\"auto-denied\"}", ""), Optional.empty());
        assertFalse(err.ok());
        assertTrue(err.text().contains("auto-denied"));
    }

    @Test
    void timeoutAndGarbage() {
        assertFalse(CliOutput.parse(CliKind.CLAUDE, new CliRunner.Result(-1, "", "", true), Optional.empty()).ok());
        CliOutput garbage = CliOutput.parse(CliKind.CLAUDE, run(0, "pas du json", ""), Optional.empty());
        assertFalse(garbage.ok());
    }

    @Test
    void longAnswersAreTruncated() {
        String text = "x".repeat(10_000);
        assertEquals(CliOutput.MAX_CHARS, CliOutput.parse(CliKind.CODEX, run(0, "", ""), Optional.of(text)).text().length());
    }
}
