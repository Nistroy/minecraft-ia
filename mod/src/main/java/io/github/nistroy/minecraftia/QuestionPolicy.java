package io.github.nistroy.minecraftia;

import java.util.Optional;
import java.util.regex.Pattern;

/** Nettoie une question joueur avant envoi au cerveau. Le texte n'est jamais passé au shell ni à la console. */
public final class QuestionPolicy {
    private static final Pattern FORMATTING = Pattern.compile("§.?");
    private static final Pattern SPACES = Pattern.compile("\\s+");
    private static final Pattern CONTROL = Pattern.compile("\\p{Cntrl}");

    private QuestionPolicy() {
    }

    public static Optional<String> clean(String raw, int maxLength) {
        if (raw == null) {
            return Optional.empty();
        }
        String text = FORMATTING.matcher(raw).replaceAll("");
        text = SPACES.matcher(text).replaceAll(" ");
        text = CONTROL.matcher(text).replaceAll("").strip();
        if (text.isEmpty() || text.length() > maxLength) {
            return Optional.empty();
        }
        return Optional.of(text);
    }
}
