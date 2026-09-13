package io.github.nistroy.minecraftia;

import io.github.nistroy.minecraftia.ItemMarkers.Icon;
import io.github.nistroy.minecraftia.ItemMarkers.Segment;
import io.github.nistroy.minecraftia.ItemMarkers.Text;
import java.util.ArrayList;
import java.util.List;
import java.util.function.ToIntFunction;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Retour à la ligne d'un texte avec icônes dans les phrases ; largeur du texte mesurée par l'appelant (police MC). */
public final class InlineLayout {
    private static final Pattern WORD = Pattern.compile("\\S+");

    public sealed interface Piece permits Word, IconPiece {
        int x();
    }

    public record Word(String text, int x) implements Piece {
    }

    public record IconPiece(Icon icon, int x) implements Piece {
    }

    public record Line(List<Piece> pieces) {
        public Line {
            pieces = List.copyOf(pieces);
        }

        public boolean hasIcon() {
            return pieces.stream().anyMatch(p -> p instanceof IconPiece);
        }
    }

    /** Mot ou icône à placer (les deux null = saut de ligne) ; spaceBefore = espace dans le texte d'origine. */
    private record Token(String word, Icon icon, boolean spaceBefore) {
        static final Token BREAK = new Token(null, null, false);
    }

    private InlineLayout() {
    }

    public static List<Line> wrap(List<Segment> segments, int maxWidth, ToIntFunction<String> width, int iconWidth) {
        List<Line> lines = new ArrayList<>();
        List<Piece> current = new ArrayList<>();
        int space = width.applyAsInt(" ");
        int x = 0;
        for (Token token : tokens(segments)) {
            if (token == Token.BREAK) {
                lines.add(new Line(current));
                current = new ArrayList<>();
                x = 0;
                continue;
            }
            int w = token.icon() != null ? iconWidth : width.applyAsInt(token.word());
            int gap = x > 0 && token.spaceBefore() ? space : 0;
            if (x > 0 && x + gap + w > maxWidth) {
                lines.add(new Line(current));
                current = new ArrayList<>();
                x = 0;
                gap = 0;
            }
            if (token.icon() != null) {
                current.add(new IconPiece(token.icon(), x + gap));
                x += gap + w;
                continue;
            }
            String rest = token.word();
            while (x == 0 && width.applyAsInt(rest) > maxWidth) {
                int cut = fit(rest, maxWidth, width);
                current.add(new Word(rest.substring(0, cut), 0));
                lines.add(new Line(current));
                current = new ArrayList<>();
                rest = rest.substring(cut);
            }
            current.add(new Word(rest, x + gap));
            x += gap + width.applyAsInt(rest);
        }
        if (!current.isEmpty()) {
            lines.add(new Line(current));
        }
        return lines;
    }

    private static List<Token> tokens(List<Segment> segments) {
        List<Token> tokens = new ArrayList<>();
        boolean pendingSpace = false;
        for (Segment segment : segments) {
            switch (segment) {
                case Icon icon -> {
                    tokens.add(new Token(null, icon, pendingSpace));
                    pendingSpace = false;
                }
                case Text text -> {
                    String[] paragraphs = text.text().split("\n", -1);
                    for (int i = 0; i < paragraphs.length; i++) {
                        if (i > 0) {
                            tokens.add(Token.BREAK);
                            pendingSpace = false;
                        }
                        Matcher word = WORD.matcher(paragraphs[i]);
                        int last = 0;
                        while (word.find()) {
                            tokens.add(new Token(word.group(), null, pendingSpace || word.start() > last));
                            pendingSpace = false;
                            last = word.end();
                        }
                        pendingSpace |= last < paragraphs[i].length();
                    }
                }
            }
        }
        return tokens;
    }

    /** Plus long début du mot qui tient sur une ligne (au moins 1 caractère, pour toujours avancer). */
    private static int fit(String word, int maxWidth, ToIntFunction<String> width) {
        int n = 1;
        while (n < word.length() && width.applyAsInt(word.substring(0, n + 1)) <= maxWidth) {
            n++;
        }
        return n;
    }
}
