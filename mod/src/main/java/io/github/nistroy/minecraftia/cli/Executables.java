package io.github.nistroy.minecraftia.cli;

import java.nio.file.InvalidPathException;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;
import java.util.function.Predicate;
import java.util.regex.Pattern;

/** Trouve une CLI installée (PATH, puis dossiers d'install connus) ; garde-fou des scripts .cmd/.bat de Windows. */
public final class Executables {
    // cmd.exe relit la ligne de commande d'un .cmd/.bat : ces caractères permettraient d'y glisser une commande.
    private static final Pattern BATCH_UNSAFE = Pattern.compile("[\"&|<>^%!\\r\\n]");

    /** Environnement de recherche, injecté pour les tests. */
    public record Env(boolean windows, Map<String, String> vars, Path home, Predicate<Path> isFile) {
        public static Env current() {
            boolean windows = System.getProperty("os.name", "").toLowerCase(Locale.ROOT).startsWith("windows");
            Predicate<Path> check = windows ? java.nio.file.Files::isRegularFile : java.nio.file.Files::isExecutable;
            return new Env(windows, System.getenv(), Path.of(System.getProperty("user.home")), check);
        }
    }

    private Executables() {
    }

    public static Optional<Path> find(String name, String configured, Env env) {
        if (configured != null && !configured.isBlank()) {
            Path path = path(configured.strip());
            return path != null && env.isFile().test(path) ? Optional.of(path) : Optional.empty();
        }
        List<String> extensions = env.windows()
                ? List.of(env.vars().getOrDefault("PATHEXT", ".COM;.EXE;.BAT;.CMD").toLowerCase(Locale.ROOT).split(";"))
                : List.of("");
        for (Path dir : dirs(env)) {
            for (String ext : extensions) {
                Path candidate = dir.resolve(name + ext);
                if (env.isFile().test(candidate)) {
                    return Optional.of(candidate);
                }
            }
        }
        return Optional.empty();
    }

    /** Arguments passables tels quels : toujours, sauf métacaractères cmd.exe pour un .cmd/.bat. */
    public static boolean safeArgs(Path executable, List<String> args) {
        String file = executable.getFileName().toString().toLowerCase(Locale.ROOT);
        if (!file.endsWith(".cmd") && !file.endsWith(".bat")) {
            return true;
        }
        return args.stream().noneMatch(a -> BATCH_UNSAFE.matcher(a).find());
    }

    private static List<Path> dirs(Env env) {
        List<Path> dirs = new ArrayList<>();
        String separator = env.windows() ? ";" : ":";
        for (String entry : env.vars().getOrDefault("PATH", "").split(separator)) {
            Path dir = entry.isBlank() ? null : path(entry.strip());
            if (dir != null) {
                dirs.add(dir);
            }
        }
        // Lanceurs de jeu au PATH réduit : emplacements par défaut de l'installeur natif et de npm.
        dirs.add(env.home().resolve(".local/bin"));
        String appData = env.vars().get("APPDATA");
        if (env.windows() && appData != null && path(appData) != null) {
            dirs.add(path(appData).resolve("npm"));
        }
        return dirs;
    }

    private static Path path(String value) {
        try {
            return Path.of(value);
        } catch (InvalidPathException e) {
            return null;
        }
    }
}
