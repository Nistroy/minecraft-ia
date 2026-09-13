package io.github.nistroy.minecraftia.net;

import io.github.nistroy.minecraftia.MinecraftIa;
import io.netty.handler.codec.DecoderException;
import net.fabricmc.fabric.api.networking.v1.PayloadTypeRegistry;
import net.minecraft.network.FriendlyByteBuf;
import net.minecraft.resources.ResourceLocation;

/** Paquets client ↔ serveur. Tailles bornées au décodage : un client modifié ne peut pas envoyer n'importe quoi. */
public final class Payloads {
    private Payloads() {
    }

    static ResourceLocation id(String path) {
        return ResourceLocation.fromNamespaceAndPath(MinecraftIa.MOD_ID, path);
    }

    /** Appelé côté client et serveur (entrypoint commun). */
    public static void register() {
        PayloadTypeRegistry.playC2S().register(AskPayload.TYPE, AskPayload.CODEC);
        PayloadTypeRegistry.playC2S().register(VotePayload.TYPE, VotePayload.CODEC);
        PayloadTypeRegistry.playC2S().register(HistoryRequestPayload.TYPE, HistoryRequestPayload.CODEC);
        PayloadTypeRegistry.playS2C().register(AnswerPayload.TYPE, AnswerPayload.CODEC);
        PayloadTypeRegistry.playS2C().register(HistoryPayload.TYPE, HistoryPayload.CODEC);
    }

    static int readCount(FriendlyByteBuf buf, int max) {
        int count = buf.readVarInt();
        if (count < 0 || count > max) {
            throw new DecoderException("liste trop longue : " + count);
        }
        return count;
    }
}
