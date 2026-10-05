package io.github.nistroy.minecraftia.cli;

import java.util.Optional;

/** CLI d'IA que le mod sait lancer chez le joueur, avec son propre abonnement. */
public enum CliKind {
    CLAUDE("claude", "claude", "Claude Code"),
    CODEX("codex", "codex", "Codex"),
    ANTIGRAVITY("agy", "agy", "Antigravity");

    private final String id;
    private final String executable;
    private final String label;

    CliKind(String id, String executable, String label) {
        this.id = id;
        this.executable = executable;
        this.label = label;
    }

    public String id() {
        return id;
    }

    public String executable() {
        return executable;
    }

    public String label() {
        return label;
    }

    public static Optional<CliKind> byId(String id) {
        for (CliKind kind : values()) {
            if (kind.id.equals(id)) {
                return Optional.of(kind);
            }
        }
        return Optional.empty();
    }
}
