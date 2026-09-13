package io.github.nistroy.minecraftia.net;

import net.minecraft.network.FriendlyByteBuf;
import net.minecraft.network.codec.StreamCodec;
import net.minecraft.network.protocol.common.custom.CustomPacketPayload;

/** Client → serveur : question posée depuis l'écran. */
public record AskPayload(String question) implements CustomPacketPayload {
    public static final int MAX_LENGTH = 512;
    public static final Type<AskPayload> TYPE = new Type<>(Payloads.id("ask"));
    public static final StreamCodec<FriendlyByteBuf, AskPayload> CODEC = CustomPacketPayload.codec(AskPayload::write, AskPayload::new);

    private AskPayload(FriendlyByteBuf buf) {
        this(buf.readUtf(MAX_LENGTH));
    }

    private void write(FriendlyByteBuf buf) {
        buf.writeUtf(question, MAX_LENGTH);
    }

    @Override
    public Type<AskPayload> type() {
        return TYPE;
    }
}
