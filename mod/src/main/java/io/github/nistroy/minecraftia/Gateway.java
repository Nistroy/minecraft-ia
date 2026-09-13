package io.github.nistroy.minecraftia;

import io.github.nistroy.minecraftia.net.AnswerPayload;
import io.github.nistroy.minecraftia.net.HistoryPayload;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ConcurrentHashMap;
import java.util.function.Supplier;
import net.fabricmc.fabric.api.networking.v1.ServerPlayNetworking;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerPlayer;

/**
 * Passerelle mince joueur ↔ cerveau. Appels HTTP asynchrones (jamais sur le tick),
 * réponses remises sur le thread serveur. Une seule recherche en cours par joueur.
 */
public final class Gateway {
    public enum Channel { CHAT, SCREEN }

    private static final int MAX_HISTORY = 50;

    private final BrainClient brain;
    private final int maxQuestionLength;
    private final String disabledReason;
    private final Set<UUID> inFlight = ConcurrentHashMap.newKeySet();

    private Gateway(BrainClient brain, int maxQuestionLength, String disabledReason) {
        this.brain = brain;
        this.maxQuestionLength = maxQuestionLength;
        this.disabledReason = disabledReason;
    }

    public static Gateway enabled(BrainClient brain, int maxQuestionLength) {
        return new Gateway(brain, maxQuestionLength, null);
    }

    public static Gateway disabled(String reason) {
        return new Gateway(null, 0, reason);
    }

    public void ask(ServerPlayer player, String raw, Channel channel) {
        if (brain == null) {
            reply(player, BrainReply.error(disabledReason), channel);
            return;
        }
        Optional<String> question = QuestionPolicy.clean(raw, maxQuestionLength);
        if (question.isEmpty()) {
            reply(player, BrainReply.notice("invalid", "Question vide ou trop longue (max " + maxQuestionLength + " caractères)."), channel);
            return;
        }
        String name = player.getGameProfile().getName();
        call(player, channel, "Je cherche…", () -> brain.ask(player.getUUID(), name, question.get()));
    }

    public void vote(ServerPlayer player, int answerId, boolean up, Channel channel) {
        if (brain == null) {
            reply(player, BrainReply.error(disabledReason), channel);
            return;
        }
        if (answerId <= 0) {
            return;
        }
        UUID id = player.getUUID();
        if (up) {
            brain.vote(id, answerId, true);
            if (channel == Channel.CHAT) {
                ChatReplies.pending(player, "Merci, vote noté ✔");
            }
            return;
        }
        call(player, channel, "Vote noté, je cherche une meilleure réponse…", () -> brain.vote(id, answerId, false)
                .thenApply(retry -> retry.orElse(BrainReply.notice("unknown", "Pas de nouvelle recherche pour cette réponse."))));
    }

    public void history(ServerPlayer player, int limit, Channel channel) {
        if (brain == null) {
            reply(player, BrainReply.error(disabledReason), channel);
            return;
        }
        UUID id = player.getUUID();
        MinecraftServer server = player.getServer();
        brain.history(id, Math.clamp(limit, 1, MAX_HISTORY)).thenAccept(items -> server.execute(() -> {
            ServerPlayer target = server.getPlayerList().getPlayer(id);
            if (target == null) {
                return;
            }
            if (channel == Channel.SCREEN && ServerPlayNetworking.canSend(target, HistoryPayload.TYPE)) {
                ServerPlayNetworking.send(target, HistoryPayload.of(items));
            } else {
                ChatReplies.history(target, items);
            }
        }));
    }

    private void call(ServerPlayer player, Channel channel, String pending, Supplier<CompletableFuture<BrainReply>> request) {
        UUID id = player.getUUID();
        if (!inFlight.add(id)) {
            reply(player, BrainReply.notice("invalid", "Une recherche est déjà en cours, patience…"), channel);
            return;
        }
        if (channel == Channel.CHAT) {
            ChatReplies.pending(player, pending);
        }
        MinecraftServer server = player.getServer();
        request.get().whenComplete((result, error) -> server.execute(() -> {
            inFlight.remove(id);
            ServerPlayer target = server.getPlayerList().getPlayer(id);
            if (target != null) {
                reply(target, error == null ? result : BrainReply.error(BrainClient.UNAVAILABLE), channel);
            }
        }));
    }

    private static void reply(ServerPlayer player, BrainReply reply, Channel channel) {
        if (channel == Channel.SCREEN && ServerPlayNetworking.canSend(player, AnswerPayload.TYPE)) {
            ServerPlayNetworking.send(player, AnswerPayload.of(reply));
        } else {
            ChatReplies.answer(player, reply);
        }
    }
}
