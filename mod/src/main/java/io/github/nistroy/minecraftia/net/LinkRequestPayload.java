package io.github.nistroy.minecraftia.net;

import net.minecraft.network.FriendlyByteBuf;
import net.minecraft.network.codec.StreamCodec;
import net.minecraft.network.protocol.common.custom.CustomPacketPayload;

/** Client → serveur : demande le lien MCP du joueur (pour la CLI d'IA lancée sur son PC). */
public record LinkRequestPayload() implements CustomPacketPayload {
    public static final Type<LinkRequestPayload> TYPE = new Type<>(Payloads.id("link_request"));
    public static final StreamCodec<FriendlyByteBuf, LinkRequestPayload> CODEC = StreamCodec.unit(new LinkRequestPayload());

    @Override
    public Type<LinkRequestPayload> type() {
        return TYPE;
    }
}
