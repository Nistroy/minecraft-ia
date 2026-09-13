package io.github.nistroy.minecraftia;

import java.util.List;

/** Réponse du cerveau. answerId &lt;= 0 : message sans réponse enregistrée (erreur, quota, attente). */
public record BrainReply(int answerId, String status, String text, List<String> sources) {
    public BrainReply {
        sources = List.copyOf(sources);
    }

    public static BrainReply notice(String status, String text) {
        return new BrainReply(-1, status, text, List.of());
    }

    public static BrainReply error(String text) {
        return notice("error", text);
    }

    public boolean hasAnswer() {
        return answerId > 0;
    }
}
