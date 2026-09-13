package io.github.nistroy.minecraftia;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import io.github.nistroy.minecraftia.InlineLayout.IconPiece;
import io.github.nistroy.minecraftia.InlineLayout.Line;
import io.github.nistroy.minecraftia.InlineLayout.Word;
import io.github.nistroy.minecraftia.ItemMarkers.Icon;
import java.util.List;
import org.junit.jupiter.api.Test;

class InlineLayoutTest {
    /** Police fictive : 6 px par caractère, espace compris ; icône 16 px. */
    private static List<Line> wrap(String text, int maxWidth) {
        return InlineLayout.wrap(ItemMarkers.parse(text), maxWidth, s -> s.length() * 6, 16);
    }

    @Test
    void wrapsWordsAtMaxWidth() {
        List<Line> lines = wrap("aa bb cc", 30);
        assertEquals(List.of(new Line(List.of(new Word("aa", 0), new Word("bb", 18))), new Line(List.of(new Word("cc", 0)))),
                lines);
    }

    @Test
    void iconSitsInTheSentenceAndPunctuationSticksToIt() {
        Line line = wrap("4 planches [[#minecraft:planks]], ok", 500).get(0);
        assertEquals(List.of(new Word("4", 0), new Word("planches", 12), new IconPiece(new Icon("minecraft:planks", true), 66),
                new Word(",", 82), new Word("ok", 94)), line.pieces());
        assertTrue(line.hasIcon());
    }

    @Test
    void iconWrapsWhenNoRoom() {
        List<Line> lines = wrap("aaaa [[minecraft:stick]]", 30);
        assertEquals(2, lines.size());
        assertFalse(lines.get(0).hasIcon());
        assertEquals(List.of(new IconPiece(new Icon("minecraft:stick", false), 0)), lines.get(1).pieces());
    }

    @Test
    void newlinesBreakAndKeepEmptyLines() {
        assertEquals(List.of(new Line(List.of(new Word("a", 0))), new Line(List.of()), new Line(List.of(new Word("b", 0)))),
                wrap("a\n\nb", 100));
    }

    @Test
    void wordLongerThanLineIsSplit() {
        assertEquals(List.of(new Line(List.of(new Word("abcde", 0))), new Line(List.of(new Word("fghij", 0)))),
                wrap("abcdefghij", 30));
    }
}
