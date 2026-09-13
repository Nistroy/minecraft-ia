package io.github.nistroy.minecraftia.net;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import io.github.nistroy.minecraftia.HistoryItem;
import io.netty.buffer.Unpooled;
import java.util.Arrays;
import java.util.List;
import net.minecraft.network.FriendlyByteBuf;
import org.junit.jupiter.api.Test;

class PayloadCodecTest {
    private static FriendlyByteBuf buffer() {
        return new FriendlyByteBuf(Unpooled.buffer());
    }

    @Test
    void askRoundTripAndLengthLimit() {
        FriendlyByteBuf buf = buffer();
        AskPayload.CODEC.encode(buf, new AskPayload("portail aether ?"));
        assertEquals(new AskPayload("portail aether ?"), AskPayload.CODEC.decode(buf));
        assertThrows(RuntimeException.class,
                () -> AskPayload.CODEC.encode(buffer(), new AskPayload("x".repeat(AskPayload.MAX_LENGTH + 1))));
    }

    @Test
    void voteAndHistoryRequestRoundTrip() {
        FriendlyByteBuf buf = buffer();
        VotePayload.CODEC.encode(buf, new VotePayload(7, false));
        assertEquals(new VotePayload(7, false), VotePayload.CODEC.decode(buf));
        HistoryRequestPayload.CODEC.encode(buf, new HistoryRequestPayload(20));
        assertEquals(new HistoryRequestPayload(20), HistoryRequestPayload.CODEC.decode(buf));
    }

    @Test
    void answerRoundTrip() {
        AnswerPayload payload = new AnswerPayload(7, "ok", "Réponse", List.of("kb:mods/aether.md", "https://x"));
        FriendlyByteBuf buf = buffer();
        AnswerPayload.CODEC.encode(buf, payload);
        assertEquals(payload, AnswerPayload.CODEC.decode(buf));
    }

    @Test
    void historyRoundTripKeepsNullVotes() {
        List<HistoryItem> items = Arrays.asList(
                new HistoryItem(7, "q1", "r1", "ok", null),
                new HistoryItem(8, "q2", "r2", "unknown", true),
                new HistoryItem(9, "q3", "r3", "ok", false));
        FriendlyByteBuf buf = buffer();
        HistoryPayload.CODEC.encode(buf, new HistoryPayload(items));
        assertEquals(new HistoryPayload(items), HistoryPayload.CODEC.decode(buf));
    }
}
