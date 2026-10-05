package io.github.nistroy.minecraftia.cli;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import java.util.Optional;

/** Réponse lisible d'une CLI : texte de l'IA, ou message d'erreur court pour le joueur. */
public record CliOutput(boolean ok, String text) {
    public static final int MAX_CHARS = 4000;

    public static CliOutput parse(CliKind kind, CliRunner.Result result, Optional<String> outputFile) {
        if (result.timedOut()) {
            return error(kind, "pas de réponse dans le délai");
        }
        return switch (kind) {
            case CLAUDE -> json(result).map(j -> bool(j, "is_error") || !string(j, "result").isPresent()
                    ? error(kind, string(j, "result").orElse(tail(result.stderr())))
                    : ok(string(j, "result").get())).orElseGet(() -> error(kind, tail(result.stderr())));
            case CODEX -> outputFile.filter(s -> !s.isBlank()).map(CliOutput::ok)
                    .orElseGet(() -> error(kind, tail(result.stderr())));
            case ANTIGRAVITY -> json(result).map(j -> "ERROR".equals(string(j, "status").orElse(""))
                    || string(j, "response").filter(s -> !s.isBlank()).isEmpty()
                    ? error(kind, string(j, "error").filter(s -> !s.isBlank()).orElse(tail(result.stderr())))
                    : ok(string(j, "response").get())).orElseGet(() -> error(kind, tail(result.stderr())));
        };
    }

    private static CliOutput ok(String text) {
        String clean = text.strip();
        return new CliOutput(true, clean.length() > MAX_CHARS ? clean.substring(0, MAX_CHARS) : clean);
    }

    private static CliOutput error(CliKind kind, String detail) {
        String text = kind.label() + " : " + (detail.isBlank() ? "échec sans message" : detail);
        return new CliOutput(false, text.length() > 400 ? text.substring(0, 400) : text);
    }

    private static Optional<JsonObject> json(CliRunner.Result result) {
        try {
            JsonElement element = JsonParser.parseString(result.stdout().strip());
            return element.isJsonObject() ? Optional.of(element.getAsJsonObject()) : Optional.empty();
        } catch (RuntimeException e) {
            return Optional.empty();
        }
    }

    private static Optional<String> string(JsonObject json, String key) {
        JsonElement value = json.get(key);
        return value != null && value.isJsonPrimitive() ? Optional.of(value.getAsString()) : Optional.empty();
    }

    private static boolean bool(JsonObject json, String key) {
        JsonElement value = json.get(key);
        return value != null && value.isJsonPrimitive() && value.getAsBoolean();
    }

    private static String tail(String stderr) {
        String clean = stderr.strip();
        return clean.length() > 300 ? clean.substring(clean.length() - 300) : clean;
    }
}
