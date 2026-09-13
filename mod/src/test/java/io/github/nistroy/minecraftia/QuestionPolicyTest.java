package io.github.nistroy.minecraftia;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.Optional;
import org.junit.jupiter.api.Test;

class QuestionPolicyTest {
    @Test
    void trimsAndCollapsesWhitespace() {
        assertEquals(Optional.of("comment aller dans l'aether ?"),
                QuestionPolicy.clean("  comment   aller\tdans l'aether ?  ", 256));
    }

    @Test
    void removesControlCharsAndFormattingCodes() {
        assertEquals(Optional.of("salut"), QuestionPolicy.clean("§csal\0ut", 256));
    }

    @Test
    void rejectsNullEmptyAndTooLong() {
        assertTrue(QuestionPolicy.clean(null, 256).isEmpty());
        assertTrue(QuestionPolicy.clean("   ", 256).isEmpty());
        assertTrue(QuestionPolicy.clean("x".repeat(257), 256).isEmpty());
        assertEquals(Optional.of("x".repeat(256)), QuestionPolicy.clean("x".repeat(256), 256));
    }
}
