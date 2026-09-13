package io.github.nistroy.minecraftia.net;

import net.minecraft.network.FriendlyByteBuf;
import net.minecraft.network.codec.StreamCodec;
import net.minecraft.network.protocol.common.custom.CustomPacketPayload;

/** Client → serveur : vote ✔ (up) / ✘ sur une réponse. */
public record VotePayload(int answerId, boolean up) implements CustomPacketPayload {
    public static final Type<VotePayload> TYPE = new Type<>(Payloads.id("vote"));
    public static final StreamCodec<FriendlyByteBuf, VotePayload> CODEC = CustomPacketPayload.codec(VotePayload::write, VotePayload::new);

    private VotePayload(FriendlyByteBuf buf) {
        this(buf.readVarInt(), buf.readBoolean());
    }

    private void write(FriendlyByteBuf buf) {
        buf.writeVarInt(answerId);
        buf.writeBoolean(up);
    }

    @Override
    public Type<VotePayload> type() {
        return TYPE;
    }
}
