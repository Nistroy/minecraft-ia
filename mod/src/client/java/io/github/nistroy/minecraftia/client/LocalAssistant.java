package io.github.nistroy.minecraftia.client;

import io.github.nistroy.minecraftia.BrainReply;
import io.github.nistroy.minecraftia.MinecraftIa;
import io.github.nistroy.minecraftia.cli.AgyConfig;
import io.github.nistroy.minecraftia.cli.CliCommand;
import io.github.nistroy.minecraftia.cli.CliKind;
import io.github.nistroy.minecraftia.cli.CliOutput;
import io.github.nistroy.minecraftia.cli.CliRunner;
import io.github.nistroy.minecraftia.cli.ClientConfig;
import io.github.nistroy.minecraftia.cli.Executables;
import io.github.nistroy.minecraftia.cli.McpLink;
import io.github.nistroy.minecraftia.net.LinkPayload;
import io.github.nistroy.minecraftia.net.LinkRequestPayload;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.stream.Stream;
import net.fabricmc.fabric.api.client.networking.v1.ClientPlayNetworking;
import net.fabricmc.loader.api.FabricLoader;
import net.minecraft.client.Minecraft;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Pose la question à la CLI d'IA du joueur (son abonnement), verrouillée sur le MCP du serveur. Lien MCP demandé au
 * serveur au premier usage. CLI lancée hors du thread du jeu ; réponse remise sur le thread client.
 */
final class LocalAssistant {
    static final LocalAssistant INSTANCE = new LocalAssistant();
    static final String SERVER_MODE = "server";
    private static final Logger LOG = LoggerFactory.getLogger(MinecraftIa.MOD_ID);

    private final ExecutorService worker = Executors.newSingleThreadExecutor(r -> {
        Thread thread = new Thread(r, "minecraft-ia-cli");
        thread.setDaemon(true);
        return thread;
    });
    private final Executables.Env env = Executables.Env.current();
    private ClientConfig config;
    private String pendingQuestion;
    private boolean pendingAuthorization;
    private boolean busy;

    private LocalAssistant() {
    }

    private ClientConfig config() {
        if (config == null) {
            Path file = FabricLoader.getInstance().getConfigDir().resolve(MinecraftIa.MOD_ID + "-client.json");
            try {
                config = ClientConfig.load(file);
            } catch (IOException e) {
                LOG.error("config client illisible ({}) : {}", file, e.toString());
                config = ClientConfig.defaults(file);
            }
        }
        return config;
    }

    List<CliKind> detected() {
        return Stream.of(CliKind.values())
                .filter(kind -> Executables.find(kind.executable(), config().path(kind), env).isPresent()).toList();
    }

    /** CLI utilisée ; vide = Gemini du serveur (aucune CLI trouvée ou choix du joueur). */
    Optional<CliKind> mode() {
        String mode = config().mode();
        List<CliKind> found = detected();
        if (SERVER_MODE.equals(mode)) {
            return Optional.empty();
        }
        if ("auto".equals(mode)) {
            return found.stream().findFirst();
        }
        return CliKind.byId(mode).filter(found::contains);
    }

    String modeLabel() {
        return mode().map(CliKind::label).orElse("Gemini (serveur)");
    }

    void cycleMode() {
        List<String> options = new ArrayList<>(detected().stream().map(CliKind::id).toList());
        options.add(SERVER_MODE);
        String current = mode().map(CliKind::id).orElse(SERVER_MODE);
        config().setMode(options.get((options.indexOf(current) + 1) % options.size()));
        save();
    }

    boolean busy() {
        return busy;
    }

    boolean needsAgyAuthorization() {
        return mode().filter(k -> k == CliKind.ANTIGRAVITY).isPresent() && !config().agyConfigured();
    }

    /** Question déjà ajoutée à la conversation par l'écran ; la réponse la complète. */
    void ask(String question) {
        CliKind kind = mode().orElseThrow();
        Optional<McpLink> link = config().link();
        if (link.isEmpty()) {
            if (!requestLink()) {
                return;
            }
            pendingQuestion = question;
            return;
        }
        run(kind, question, link.get());
    }

    void authorizeAgy() {
        Optional<McpLink> link = config().link();
        if (link.isEmpty()) {
            if (requestLink()) {
                pendingAuthorization = true;
            }
            return;
        }
        busy = true;
        McpLink current = link.get();
        worker.execute(() -> {
            Optional<String> failure = configureAgy(current);
            Minecraft.getInstance().execute(() -> {
                busy = false;
                if (failure.isEmpty()) {
                    config().setAgyConfigured(true);
                    save();
                }
                ClientState.INSTANCE.onAnswer(failure.map(BrainReply::error).orElseGet(() -> BrainReply.notice("ok",
                        "Antigravity autorisé : seuls le serveur MCP minecraft-ia et la règle " + "mcp(minecraft-ia/*) ont été "
                                + "ajoutés à sa config. Pose ta question.")));
            });
        });
    }

    /** Demande au serveur ; faux (et erreur affichée) si son mod est trop ancien pour donner des liens. */
    private boolean requestLink() {
        if (!ClientPlayNetworking.canSend(LinkRequestPayload.TYPE)) {
            ClientState.INSTANCE.onAnswer(BrainReply.error("Le serveur n'a pas encore la version du mod qui donne les liens MCP."));
            return false;
        }
        busy = true;
        ClientPlayNetworking.send(new LinkRequestPayload());
        return true;
    }

    void onLink(LinkPayload payload) {
        String question = pendingQuestion;
        boolean authorize = pendingAuthorization;
        pendingQuestion = null;
        pendingAuthorization = false;
        busy = false;
        if (!payload.error().isEmpty()) {
            ClientState.INSTANCE.onAnswer(BrainReply.error(payload.error()));
            return;
        }
        McpLink link;
        try {
            link = new McpLink(payload.url(), payload.token());
        } catch (IllegalArgumentException e) {
            ClientState.INSTANCE.onAnswer(BrainReply.error("Lien MCP reçu invalide : " + e.getMessage()));
            return;
        }
        config().setLink(link);
        save();
        if (authorize) {
            authorizeAgy();
        } else if (question != null) {
            Optional<CliKind> kind = mode();
            if (kind.isEmpty() || needsAgyAuthorization()) {
                ClientState.INSTANCE.onAnswer(BrainReply.notice("ok", "Lien MCP reçu. Clique sur « Autoriser » puis repose ta question."));
            } else {
                run(kind.get(), question, link);
            }
        }
    }

    private void run(CliKind kind, String question, McpLink link) {
        busy = true;
        int timeout = config().timeoutSeconds();
        String configured = config().path(kind);
        worker.execute(() -> {
            CliOutput output = execute(kind, configured, question, link, timeout);
            Minecraft.getInstance().execute(() -> {
                busy = false;
                ClientState.INSTANCE.onAnswer(output.ok() ? BrainReply.notice("ok", output.text()) : BrainReply.error(output.text()));
            });
        });
    }

    private CliOutput execute(CliKind kind, String configured, String question, McpLink link, int timeout) {
        Optional<Path> exe = Executables.find(kind.executable(), configured, env);
        if (exe.isEmpty()) {
            return new CliOutput(false, kind.label() + " introuvable sur ce PC.");
        }
        if (kind == CliKind.ANTIGRAVITY) {
            Optional<String> refusal = AgyConfig.refusal(readAgySettings());
            if (refusal.isPresent()) {
                return new CliOutput(false, refusal.get());
            }
        }
        Path work = null;
        try {
            work = Files.createTempDirectory("minecraft-ia-");
            CliCommand.Invocation invocation = CliCommand.build(kind, question, link, work, timeout);
            if (!Executables.safeArgs(exe.get(), invocation.args())) {
                return new CliOutput(false, "Question refusée : caractères interdits pour lancer " + kind.label() + ".");
            }
            for (Map.Entry<String, String> file : invocation.files().entrySet()) {
                Files.writeString(work.resolve(file.getKey()), file.getValue());
            }
            List<String> command = new ArrayList<>();
            command.add(exe.get().toString());
            command.addAll(invocation.args());
            CliRunner.Result result = CliRunner.run(command, work, invocation.env(), invocation.stdin().orElse(null),
                    Duration.ofSeconds(timeout + 15));
            Optional<String> output = Optional.empty();
            if (invocation.outputFile().isPresent() && Files.exists(work.resolve(invocation.outputFile().get()))) {
                output = Optional.of(Files.readString(work.resolve(invocation.outputFile().get())));
            }
            return CliOutput.parse(kind, result, output);
        } catch (IOException e) {
            LOG.warn("{} non lancé : {}", kind.label(), e.toString());
            return new CliOutput(false, kind.label() + " n'a pas pu être lancé : " + e.getMessage());
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            return new CliOutput(false, "Recherche interrompue.");
        } finally {
            delete(work);
        }
    }

    private Optional<String> configureAgy(McpLink link) {
        Optional<Path> exe = Executables.find(CliKind.ANTIGRAVITY.executable(), config().path(CliKind.ANTIGRAVITY), env);
        if (exe.isEmpty()) {
            return Optional.of("Antigravity introuvable sur ce PC.");
        }
        Optional<String> refusal = AgyConfig.refusal(readAgySettings());
        if (refusal.isPresent()) {
            return refusal;
        }
        Path work = null;
        try {
            work = Files.createTempDirectory("minecraft-ia-");
            List<String> args = AgyConfig.mcpAddArgs(link);
            if (!Executables.safeArgs(exe.get(), args)) {
                return Optional.of("Lien MCP inattendu pour Antigravity.");
            }
            List<String> command = new ArrayList<>();
            command.add(exe.get().toString());
            command.addAll(args);
            CliRunner.Result result = CliRunner.run(command, work, Map.of(), null, Duration.ofSeconds(60));
            if (result.timedOut() || result.exitCode() != 0) {
                return Optional.of("Antigravity : ajout du MCP refusé (" + result.stderr().strip() + ")");
            }
            Path settings = AgyConfig.settingsFile(home());
            Files.createDirectories(settings.getParent());
            Files.writeString(settings, AgyConfig.withMcpAllowed(readAgySettings()));
            return Optional.empty();
        } catch (IOException | RuntimeException e) {
            return Optional.of("Antigravity : configuration impossible (" + e.getMessage() + ")");
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            return Optional.of("Configuration interrompue.");
        } finally {
            delete(work);
        }
    }

    private String readAgySettings() {
        Path settings = AgyConfig.settingsFile(home());
        try {
            return Files.exists(settings) ? Files.readString(settings) : "";
        } catch (IOException e) {
            return "{illisible";
        }
    }

    private static Path home() {
        return Path.of(System.getProperty("user.home"));
    }

    private void save() {
        try {
            config().save();
        } catch (IOException e) {
            LOG.warn("config client non sauvée : {}", e.toString());
        }
    }

    private static void delete(Path dir) {
        if (dir == null) {
            return;
        }
        try (Stream<Path> paths = Files.walk(dir)) {
            paths.sorted(Comparator.reverseOrder()).forEach(p -> p.toFile().delete());
        } catch (IOException e) {
            LOG.debug("dossier temporaire non supprimé : {}", dir);
        }
    }
}
