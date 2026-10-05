package io.github.nistroy.minecraftia.cli;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Path;
import java.time.Duration;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.DisabledOnOs;
import org.junit.jupiter.api.condition.OS;
import org.junit.jupiter.api.io.TempDir;

@DisabledOnOs(OS.WINDOWS)
class CliRunnerTest {
    @TempDir
    Path dir;

    @Test
    void passesStdinEnvAndWorkDir() throws Exception {
        CliRunner.Result result = CliRunner.run(List.of("/bin/sh", "-c", "cat; printf ' %s %s' \"$IA_X\" \"$(pwd -P)\""),
                dir, Map.of("IA_X", "ok"), "bonjour é", Duration.ofSeconds(10));
        assertEquals(0, result.exitCode());
        assertEquals("bonjour é ok " + dir.toRealPath(), result.stdout());
    }

    @Test
    void killsOnTimeout() throws Exception {
        long start = System.nanoTime();
        CliRunner.Result result = CliRunner.run(List.of("/bin/sh", "-c", "sleep 30"), dir, Map.of(), null, Duration.ofMillis(300));
        assertTrue(result.timedOut());
        assertTrue(Duration.ofNanos(System.nanoTime() - start).toSeconds() < 10);
    }

    @Test
    void capturesStderrAndExitCode() throws Exception {
        CliRunner.Result result = CliRunner.run(List.of("/bin/sh", "-c", "echo oups >&2; exit 3"), dir, Map.of(), null,
                Duration.ofSeconds(10));
        assertEquals(3, result.exitCode());
        assertEquals("oups\n", result.stderr());
    }
}
