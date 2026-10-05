package io.github.nistroy.minecraftia.net;

import io.github.nistroy.minecraftia.McpLinkReply;
import net.minecraft.network.FriendlyByteBuf;
import net.minecraft.network.codec.StreamCodec;
import net.minecraft.network.protocol.common.custom.CustomPacketPayload;

/** Serveur → client : lien MCP du joueur (envoyé à lui seul), ou erreur. */
public record LinkPayload(String url, String token, String error) implements CustomPacketPayload {
    public static final Type<LinkPayload> TYPE = new Type<>(Payloads.id("link"));
    public static final StreamCodec<FriendlyByteBuf, LinkPayload> CODEC = CustomPacketPayload.codec(LinkPayload::write, LinkPayload::new);
    private static final int MAX = 256;

    private LinkPayload(FriendlyByteBuf buf) {
        this(buf.readUtf(MAX), buf.readUtf(MAX), buf.readUtf(MAX));
    }

    public static LinkPayload of(McpLinkReply reply) {
        return new LinkPayload(reply.url(), reply.token(), reply.error());
    }

    private void write(FriendlyByteBuf buf) {
        buf.writeUtf(url, MAX);
        buf.writeUtf(token, MAX);
        buf.writeUtf(error, MAX);
    }

    @Override
    public Type<LinkPayload> type() {
        return TYPE;
    }
}
