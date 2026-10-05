package io.github.nistroy.minecraftia.cli;

import static java.nio.charset.StandardCharsets.UTF_8;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.file.Path;
import java.time.Duration;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;

/** Lance une CLI : stdin écrit puis fermé, stdout/stderr lus en parallèle (pas d'interblocage), tuée au délai. */
public final class CliRunner {
    static final int MAX_OUTPUT = 256 * 1024;

    public record Result(int exitCode, String stdout, String stderr, boolean timedOut) {
    }

    private CliRunner() {
    }

    public static Result run(List<String> command, Path dir, Map<String, String> env, String stdin, Duration timeout)
            throws IOException, InterruptedException {
        ProcessBuilder builder = new ProcessBuilder(command).directory(dir.toFile());
        builder.environment().putAll(env);
        Process process = builder.start();
        CompletableFuture<String> out = CompletableFuture.supplyAsync(() -> read(process.getInputStream()));
        CompletableFuture<String> err = CompletableFuture.supplyAsync(() -> read(process.getErrorStream()));
        try (OutputStream in = process.getOutputStream()) {
            if (stdin != null) {
                in.write(stdin.getBytes(UTF_8));
            }
        } catch (IOException e) {
            // CLI déjà sortie sans lire stdin : son code et sa sortie d'erreur disent pourquoi.
        }
        if (!process.waitFor(timeout.toMillis(), TimeUnit.MILLISECONDS)) {
            process.descendants().forEach(ProcessHandle::destroyForcibly);
            process.destroyForcibly();
            return new Result(-1, "", "", true);
        }
        return new Result(process.exitValue(), collect(out), collect(err), false);
    }

    private static String read(InputStream stream) {
        try (stream) {
            byte[] bytes = stream.readNBytes(MAX_OUTPUT);
            stream.transferTo(OutputStream.nullOutputStream());
            return new String(bytes, UTF_8);
        } catch (IOException e) {
            return "";
        }
    }

    private static String collect(CompletableFuture<String> stream) throws InterruptedException {
        try {
            return stream.get(5, TimeUnit.SECONDS);
        } catch (ExecutionException | TimeoutException e) {
            return "";
        }
    }
}
