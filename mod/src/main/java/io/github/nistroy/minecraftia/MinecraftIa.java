package io.github.nistroy.minecraftia;

import io.github.nistroy.minecraftia.net.AskPayload;
import io.github.nistroy.minecraftia.net.HistoryRequestPayload;
import io.github.nistroy.minecraftia.net.Payloads;
import io.github.nistroy.minecraftia.net.VotePayload;
import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.function.Supplier;
import net.fabricmc.api.EnvType;
import net.fabricmc.api.ModInitializer;
import net.fabricmc.fabric.api.command.v2.CommandRegistrationCallback;
import net.fabricmc.fabric.api.networking.v1.ServerPlayNetworking;
import net.fabricmc.loader.api.FabricLoader;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public final class MinecraftIa implements ModInitializer {
    public static final String MOD_ID = "minecraft_ia";
    private static final Logger LOG = LoggerFactory.getLogger(MOD_ID);

    @Override
    public void onInitialize() {
        Payloads.register();
        // Passerelle sur serveur dédié seulement : en solo, pas de cerveau sur la machine du joueur.
        if (FabricLoader.getInstance().getEnvironmentType() != EnvType.SERVER) {
            return;
        }
        Gateway gateway = createGateway();
        CommandRegistrationCallback.EVENT.register((dispatcher, registryAccess, environment) -> IaCommand.register(dispatcher, gateway));
        ServerPlayNetworking.registerGlobalReceiver(AskPayload.TYPE,
                (payload, context) -> gateway.ask(context.player(), payload.question(), Gateway.Channel.SCREEN));
        ServerPlayNetworking.registerGlobalReceiver(VotePayload.TYPE,
                (payload, context) -> gateway.vote(context.player(), payload.answerId(), payload.up(), Gateway.Channel.SCREEN));
        ServerPlayNetworking.registerGlobalReceiver(HistoryRequestPayload.TYPE,
                (payload, context) -> gateway.history(context.player(), payload.limit(), Gateway.Channel.SCREEN));
    }

    private static Gateway createGateway() {
        Path file = FabricLoader.getInstance().getConfigDir().resolve(MOD_ID + ".json");
        try {
            ModConfig config = ModConfig.load(file, Path.of(System.getProperty("user.home")));
            // Relu à chaque appel : le cerveau peut régénérer son jeton sans redémarrer Minecraft.
            Supplier<String> token = () -> {
                try {
                    return Files.readString(config.tokenFile()).strip();
                } catch (IOException e) {
                    throw new UncheckedIOException(e);
                }
            };
            LOG.info("Assistant IA : cerveau {}", config.brainUrl());
            return Gateway.enabled(new BrainClient(config.brainUrl(), token, config.timeout()), config.maxQuestionLength());
        } catch (IOException | IllegalArgumentException e) {
            LOG.error("Assistant IA désactivé : {} ({})", e.getMessage(), file);
            return Gateway.disabled("Assistant IA désactivé (config invalide, voir logs serveur).");
        }
    }
}
