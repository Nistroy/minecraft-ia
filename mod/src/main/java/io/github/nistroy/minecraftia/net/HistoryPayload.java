package io.github.nistroy.minecraftia.net;

import io.github.nistroy.minecraftia.HistoryItem;
import io.github.nistroy.minecraftia.Texts;
import java.util.ArrayList;
import java.util.List;
import net.minecraft.network.FriendlyByteBuf;
import net.minecraft.network.codec.StreamCodec;
import net.minecraft.network.protocol.common.custom.CustomPacketPayload;

/** Serveur → client : historique perso. */
public record HistoryPayload(List<HistoryItem> items) implements CustomPacketPayload {
    public static final int MAX_ITEMS = 50;
    public static final int MAX_QUESTION = AskPayload.MAX_LENGTH;
    public static final Type<HistoryPayload> TYPE = new Type<>(Payloads.id("history"));
    public static final StreamCodec<FriendlyByteBuf, HistoryPayload> CODEC = CustomPacketPayload.codec(HistoryPayload::write, HistoryPayload::new);

    public HistoryPayload {
        items = List.copyOf(items);
    }

    private HistoryPayload(FriendlyByteBuf buf) {
        this(readItems(buf));
    }

    public static HistoryPayload of(List<HistoryItem> items) {
        return new HistoryPayload(items.stream().limit(MAX_ITEMS).map(i -> new HistoryItem(i.answerId(),
                Texts.truncate(i.question(), MAX_QUESTION), Texts.truncate(i.text(), AnswerPayload.MAX_TEXT),
                Texts.truncate(i.status(), AnswerPayload.MAX_STATUS), i.vote())).toList());
    }

    private static List<HistoryItem> readItems(FriendlyByteBuf buf) {
        int count = Payloads.readCount(buf, MAX_ITEMS);
        List<HistoryItem> items = new ArrayList<>(count);
        for (int i = 0; i < count; i++) {
            int id = buf.readVarInt();
            String question = buf.readUtf(MAX_QUESTION);
            String text = buf.readUtf(AnswerPayload.MAX_TEXT);
            String status = buf.readUtf(AnswerPayload.MAX_STATUS);
            byte vote = buf.readByte();
            items.add(new HistoryItem(id, question, text, status, vote < 0 ? null : vote == 1));
        }
        return items;
    }

    private void write(FriendlyByteBuf buf) {
        buf.writeVarInt(items.size());
        for (HistoryItem item : items) {
            buf.writeVarInt(item.answerId());
            buf.writeUtf(item.question(), MAX_QUESTION);
            buf.writeUtf(item.text(), AnswerPayload.MAX_TEXT);
            buf.writeUtf(item.status(), AnswerPayload.MAX_STATUS);
            buf.writeByte(item.vote() == null ? -1 : item.vote() ? 1 : 0);
        }
    }

    @Override
    public Type<HistoryPayload> type() {
        return TYPE;
    }
}
