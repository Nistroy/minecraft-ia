package io.github.nistroy.minecraftia.net;

import net.minecraft.network.FriendlyByteBuf;
import net.minecraft.network.codec.StreamCodec;
import net.minecraft.network.protocol.common.custom.CustomPacketPayload;

/** Client → serveur : demande l'historique perso (limit bornée côté serveur). */
public record HistoryRequestPayload(int limit) implements CustomPacketPayload {
    public static final Type<HistoryRequestPayload> TYPE = new Type<>(Payloads.id("history_request"));
    public static final StreamCodec<FriendlyByteBuf, HistoryRequestPayload> CODEC =
            CustomPacketPayload.codec(HistoryRequestPayload::write, HistoryRequestPayload::new);

    private HistoryRequestPayload(FriendlyByteBuf buf) {
        this(buf.readVarInt());
    }

    private void write(FriendlyByteBuf buf) {
        buf.writeVarInt(limit);
    }

    @Override
    public Type<HistoryRequestPayload> type() {
        return TYPE;
    }
}
