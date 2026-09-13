package io.github.nistroy.minecraftia.net;

import io.github.nistroy.minecraftia.BrainReply;
import io.github.nistroy.minecraftia.Texts;
import java.util.ArrayList;
import java.util.List;
import net.minecraft.network.FriendlyByteBuf;
import net.minecraft.network.codec.StreamCodec;
import net.minecraft.network.protocol.common.custom.CustomPacketPayload;

/** Serveur → client : réponse (ou erreur / quota) pour l'écran. */
public record AnswerPayload(int answerId, String status, String text, List<String> sources) implements CustomPacketPayload {
    public static final int MAX_STATUS = 16;
    public static final int MAX_TEXT = 4096;
    public static final int MAX_SOURCES = 16;
    public static final int MAX_SOURCE = 512;
    public static final Type<AnswerPayload> TYPE = new Type<>(Payloads.id("answer"));
    public static final StreamCodec<FriendlyByteBuf, AnswerPayload> CODEC = CustomPacketPayload.codec(AnswerPayload::write, AnswerPayload::new);

    public AnswerPayload {
        sources = List.copyOf(sources);
    }

    private AnswerPayload(FriendlyByteBuf buf) {
        this(buf.readVarInt(), buf.readUtf(MAX_STATUS), buf.readUtf(MAX_TEXT), readSources(buf));
    }

    public static AnswerPayload of(BrainReply reply) {
        List<String> sources = reply.sources().stream().limit(MAX_SOURCES).map(s -> Texts.truncate(s, MAX_SOURCE)).toList();
        return new AnswerPayload(reply.answerId(), Texts.truncate(reply.status(), MAX_STATUS),
                Texts.truncate(reply.text(), MAX_TEXT), sources);
    }

    public BrainReply toReply() {
        return new BrainReply(answerId, status, text, sources);
    }

    private static List<String> readSources(FriendlyByteBuf buf) {
        int count = Payloads.readCount(buf, MAX_SOURCES);
        List<String> sources = new ArrayList<>(count);
        for (int i = 0; i < count; i++) {
            sources.add(buf.readUtf(MAX_SOURCE));
        }
        return sources;
    }

    private void write(FriendlyByteBuf buf) {
        buf.writeVarInt(answerId);
        buf.writeUtf(status, MAX_STATUS);
        buf.writeUtf(text, MAX_TEXT);
        buf.writeVarInt(sources.size());
        sources.forEach(s -> buf.writeUtf(s, MAX_SOURCE));
    }

    @Override
    public Type<AnswerPayload> type() {
        return TYPE;
    }
}
