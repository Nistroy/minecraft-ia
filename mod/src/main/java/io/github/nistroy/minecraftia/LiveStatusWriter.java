package io.github.nistroy.minecraftia;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.time.Instant;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerLifecycleEvents;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerTickEvents;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerPlayer;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/** Toutes les 5 s : TPS + positions dans un fichier JSON local, lu par le MCP. Écriture hors du thread serveur. */
public final class LiveStatusWriter {
    private static final Logger LOG = LoggerFactory.getLogger(MinecraftIa.MOD_ID);
    private static final int PERIOD_TICKS = 100;

    private final Path file;
    private final ExecutorService io = Executors.newSingleThreadExecutor(r -> {
        Thread thread = new Thread(r, "minecraft-ia-live");
        thread.setDaemon(true);
        return thread;
    });
    private int ticks;
    private boolean warned;

    public LiveStatusWriter(Path file) {
        this.file = file;
    }

    public void register() {
        ServerTickEvents.END_SERVER_TICK.register(this::onTick);
        ServerLifecycleEvents.SERVER_STOPPING.register(server -> io.shutdown());
    }

    private void onTick(MinecraftServer server) {
        if (++ticks % PERIOD_TICKS != 0) {
            return;
        }
        long nanos = server.getAverageTickTimeNanos();
        var players = server.getPlayerList().getPlayers().stream().map(LiveStatusWriter::position).toList();
        LiveSnapshot snapshot = new LiveSnapshot(Instant.now().getEpochSecond(),
                LiveSnapshot.tps(server.tickRateManager().tickrate(), nanos), LiveSnapshot.mspt(nanos), players);
        String json = snapshot.toJson();
        io.execute(() -> write(json));
    }

    private static LiveSnapshot.PlayerPos position(ServerPlayer player) {
        return new LiveSnapshot.PlayerPos(player.getGameProfile().getName(),
                player.level().dimension().location().toString(), player.getBlockX(), player.getBlockY(), player.getBlockZ());
    }

    private void write(String json) {
        try {
            Files.createDirectories(file.toAbsolutePath().getParent());
            Path tmp = file.resolveSibling(file.getFileName() + ".tmp");
            Files.writeString(tmp, json);
            Files.move(tmp, file, StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
            warned = false;
        } catch (IOException e) {
            if (!warned) {
                LOG.warn("statut live non écrit ({}) : {}", file, e.toString());
                warned = true;
            }
        }
    }
}
