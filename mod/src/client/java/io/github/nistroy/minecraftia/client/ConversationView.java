package io.github.nistroy.minecraftia.client;

import io.github.nistroy.minecraftia.HistoryItem;
import io.github.nistroy.minecraftia.InlineLayout;
import io.github.nistroy.minecraftia.InlineLayout.IconPiece;
import io.github.nistroy.minecraftia.InlineLayout.Line;
import io.github.nistroy.minecraftia.InlineLayout.Word;
import io.github.nistroy.minecraftia.ItemMarkers;
import io.github.nistroy.minecraftia.SourceLabel;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import java.util.function.Function;
import java.util.stream.Collectors;
import net.minecraft.Util;
import net.minecraft.client.gui.Font;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.network.chat.Component;
import net.minecraft.util.FormattedCharSequence;
import net.minecraft.world.item.ItemStack;

/** Conversation mise en page : bulles question, réponses avec icônes dans le texte et grilles de craft, défilement. */
final class ConversationView {
    private static final int GAP = 6;
    private static final int PAD = 5;
    private static final int BAR = 3;
    private static final int SCROLLBAR = 3;
    private static final int TEXT_LINE = 10;
    private static final int ICON_LINE = 18;
    private static final int ICON = 16;
    private static final int MAX_GRIDS = 2;
    private static final int SCROLL_STEP = 20;
    private static final int WHITE = 0xFFFFFFFF;
    private static final int GRAY = 0xFFAAAAAA;
    private static final int YELLOW = 0xFFFFFF55;
    private static final int RED = 0xFFFF5555;
    private static final int GREEN = 0xFF55FF55;
    private static final int QUESTION_BG = 0xFF2E3A59;
    private static final int ANSWER_BG = 0x50000000;
    private static final int TRACK = 0x40FFFFFF;
    private static final int THUMB = 0xC0FFFFFF;

    /** Élément vertical déjà mis en page pour la largeur courante. */
    private interface Block {
        int height();

        /** Dessine en (x, y) ; renvoie l'item sous la souris (info-bulle) ou EMPTY. */
        ItemStack render(GuiGraphics graphics, int x, int y, int mouseX, int mouseY);
    }

    private final Font font;
    private final ItemIcons icons;
    private int x;
    private int y;
    private int width;
    private int height;
    private List<Block> blocks = List.of();
    private int scroll;

    ConversationView(Font font, ItemIcons icons) {
        this.font = font;
        this.icons = icons;
    }

    void setBounds(int x, int y, int width, int height) {
        this.x = x;
        this.y = y;
        this.width = width;
        this.height = height;
    }

    void showConversation(List<ClientState.Entry> entries, Function<String, Optional<CraftingGrid>> grids) {
        List<Block> out = new ArrayList<>();
        if (entries.isEmpty()) {
            out.add(notice(tr("screen.minecraft_ia.empty"), false));
        }
        for (ClientState.Entry entry : entries) {
            out.add(question(entry.question != null ? entry.question : tr("screen.minecraft_ia.retry")));
            if (entry.reply == null) {
                out.add(notice(tr("screen.minecraft_ia.searching"), true));
                continue;
            }
            List<CraftingGrid> found = entry.reply.sources().stream().map(SourceLabel::recipeId).flatMap(Optional::stream)
                    .map(grids).flatMap(Optional::stream).limit(MAX_GRIDS).toList();
            out.add(answer(entry.reply.text(), entry.reply.status(), found, entry.reply.sources(), entry.vote));
        }
        show(out, true);
    }

    /** Historique du cerveau (plus récent en haut) : pas de sources transmises, donc pas de grille. */
    void showHistory(List<HistoryItem> items) {
        List<Block> out = new ArrayList<>();
        if (items.isEmpty()) {
            out.add(notice(tr("screen.minecraft_ia.history_empty"), false));
        }
        for (HistoryItem item : items) {
            out.add(question(item.question()));
            out.add(answer(item.text(), item.status(), List.of(), List.of(), item.vote()));
        }
        show(out, false);
    }

    boolean mouseScrolled(double scrollY) {
        scroll = Math.clamp(scroll - Math.round(scrollY * SCROLL_STEP), 0, maxScroll());
        return true;
    }

    void render(GuiGraphics graphics, int mouseX, int mouseY) {
        boolean inside = inside(mouseX, mouseY, x, y, width, height);
        int mx = inside ? mouseX : Integer.MIN_VALUE;
        int my = inside ? mouseY : Integer.MIN_VALUE;
        ItemStack hovered = ItemStack.EMPTY;
        graphics.enableScissor(x, y, x + width, y + height);
        int blockY = y - scroll;
        for (Block block : blocks) {
            int h = block.height();
            if (blockY + h > y && blockY < y + height) {
                ItemStack over = block.render(graphics, x, blockY, mx, my);
                if (!over.isEmpty()) {
                    hovered = over;
                }
            }
            blockY += h + GAP;
        }
        graphics.disableScissor();
        renderScrollbar(graphics);
        if (!hovered.isEmpty()) {
            graphics.renderTooltip(font, hovered, mouseX, mouseY);
        }
    }

    private void show(List<Block> blocks, boolean scrollToEnd) {
        this.blocks = List.copyOf(blocks);
        scroll = scrollToEnd ? maxScroll() : 0;
    }

    private int contentWidth() {
        return width - SCROLLBAR - 3;
    }

    private int contentHeight() {
        return blocks.stream().mapToInt(Block::height).sum() + Math.max(0, blocks.size() - 1) * GAP;
    }

    private int maxScroll() {
        return Math.max(0, contentHeight() - height);
    }

    private void renderScrollbar(GuiGraphics graphics) {
        int content = contentHeight();
        if (content <= height) {
            return;
        }
        int thumb = Math.max(12, height * height / content);
        int thumbY = y + (height - thumb) * scroll / maxScroll();
        graphics.fill(x + width - SCROLLBAR, y, x + width, y + height, TRACK);
        graphics.fill(x + width - SCROLLBAR, thumbY, x + width, thumbY + thumb, THUMB);
    }

    private Block question(String text) {
        List<FormattedCharSequence> lines = font.split(Component.literal(text), contentWidth() * 3 / 4 - 2 * PAD);
        int textWidth = lines.stream().mapToInt(font::width).max().orElse(0);
        int h = lines.size() * TEXT_LINE + 2 * PAD - 2;
        return new Block() {
            @Override
            public int height() {
                return h;
            }

            @Override
            public ItemStack render(GuiGraphics graphics, int bx, int by, int mouseX, int mouseY) {
                int right = bx + contentWidth();
                int left = right - textWidth - 2 * PAD;
                graphics.fill(left, by, right, by + h, QUESTION_BG);
                for (int i = 0; i < lines.size(); i++) {
                    graphics.drawString(font, lines.get(i), left + PAD, by + PAD + i * TEXT_LINE, WHITE);
                }
                return ItemStack.EMPTY;
            }
        };
    }

    private Block answer(String text, String status, List<CraftingGrid> grids, List<String> sources, Boolean vote) {
        int inner = contentWidth() - BAR - 2 * PAD;
        List<Line> lines = InlineLayout.wrap(ItemMarkers.parse(text), inner, font::width, ICON);
        List<FormattedCharSequence> sourceLines = sources.isEmpty() ? List.of()
                : font.split(Component.literal(tr("screen.minecraft_ia.sources")
                        + sources.stream().map(s -> SourceLabel.of(s).label()).collect(Collectors.joining(", "))), inner);
        int textColor = switch (status) {
            case "ok" -> WHITE;
            case "unknown" -> YELLOW;
            default -> RED;
        };
        int barColor = switch (status) {
            case "ok" -> GREEN;
            case "unknown" -> YELLOW;
            default -> RED;
        };
        int h = PAD + lines.stream().mapToInt(ConversationView::lineHeight).sum()
                + grids.size() * (GAP + CraftingGrid.HEIGHT)
                + (sourceLines.isEmpty() ? 0 : 3 + sourceLines.size() * TEXT_LINE)
                + (vote == null ? 0 : TEXT_LINE) + PAD - 2;
        return new Block() {
            @Override
            public int height() {
                return h;
            }

            @Override
            public ItemStack render(GuiGraphics graphics, int bx, int by, int mouseX, int mouseY) {
                ItemStack hovered = ItemStack.EMPTY;
                graphics.fill(bx, by, bx + contentWidth(), by + h, ANSWER_BG);
                graphics.fill(bx, by, bx + BAR, by + h, barColor);
                int cx = bx + BAR + PAD;
                int cy = by + PAD;
                for (Line line : lines) {
                    int lh = lineHeight(line);
                    for (InlineLayout.Piece piece : line.pieces()) {
                        switch (piece) {
                            case Word word -> graphics.drawString(font, word.text(), cx + word.x(), cy + (lh - TEXT_LINE) / 2, textColor);
                            case IconPiece icon -> {
                                ItemStack stack = icons.current(icon.icon());
                                int iconX = cx + icon.x();
                                int iconY = cy + (lh - ICON) / 2;
                                graphics.renderItem(stack, iconX, iconY);
                                if (!stack.isEmpty() && inside(mouseX, mouseY, iconX, iconY, ICON, ICON)) {
                                    hovered = stack;
                                }
                            }
                        }
                    }
                    cy += lh;
                }
                for (CraftingGrid grid : grids) {
                    cy += GAP;
                    ItemStack over = grid.render(graphics, font, cx, cy, mouseX, mouseY);
                    if (!over.isEmpty()) {
                        hovered = over;
                    }
                    cy += CraftingGrid.HEIGHT;
                }
                if (!sourceLines.isEmpty()) {
                    cy += 3;
                    for (FormattedCharSequence source : sourceLines) {
                        graphics.drawString(font, source, cx, cy, GRAY);
                        cy += TEXT_LINE;
                    }
                }
                if (vote != null) {
                    graphics.drawString(font, vote ? "✔" : "✘", cx, cy, vote ? GREEN : RED);
                }
                return hovered;
            }
        };
    }

    /** Message gris ; animé = « Je cherche » avec des points qui défilent. */
    private Block notice(String text, boolean animated) {
        List<FormattedCharSequence> lines = font.split(Component.literal(text), contentWidth());
        int h = lines.size() * TEXT_LINE;
        return new Block() {
            @Override
            public int height() {
                return h;
            }

            @Override
            public ItemStack render(GuiGraphics graphics, int bx, int by, int mouseX, int mouseY) {
                if (animated) {
                    String dots = ".".repeat((int) (Util.getMillis() / 400 % 4));
                    graphics.drawString(font, text.replace("…", "") + dots, bx, by, GRAY);
                    return ItemStack.EMPTY;
                }
                for (int i = 0; i < lines.size(); i++) {
                    graphics.drawString(font, lines.get(i), bx, by + i * TEXT_LINE, GRAY);
                }
                return ItemStack.EMPTY;
            }
        };
    }

    private static int lineHeight(Line line) {
        return line.hasIcon() ? ICON_LINE : TEXT_LINE;
    }

    private static boolean inside(int px, int py, int x, int y, int w, int h) {
        return px >= x && px < x + w && py >= y && py < y + h;
    }

    private static String tr(String key) {
        return Component.translatable(key).getString();
    }
}
