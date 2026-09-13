package io.github.nistroy.minecraftia.client;

import io.github.nistroy.minecraftia.HistoryItem;
import io.github.nistroy.minecraftia.SourceLabel;
import io.github.nistroy.minecraftia.net.AskPayload;
import io.github.nistroy.minecraftia.net.HistoryRequestPayload;
import io.github.nistroy.minecraftia.net.VotePayload;
import java.util.ArrayList;
import java.util.List;
import java.util.stream.Collectors;
import net.fabricmc.fabric.api.client.networking.v1.ClientPlayNetworking;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.client.gui.components.Button;
import net.minecraft.client.gui.components.EditBox;
import net.minecraft.client.gui.components.Tooltip;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.network.chat.Component;
import net.minecraft.util.FormattedCharSequence;
import org.lwjgl.glfw.GLFW;

/** Écran de l'assistant : question, conversation de la session, historique perso, votes ✔/✘. */
final class AssistantScreen extends Screen {
    private static final int MAX_WIDTH = 380;
    private static final int TOP = 30;
    private static final int WHITE = 0xFFFFFFFF;
    private static final int GRAY = 0xFFAAAAAA;
    private static final int YELLOW = 0xFFFFFF55;
    private static final int RED = 0xFFFF5555;
    private static final int HISTORY_LIMIT = 20;

    private record Line(FormattedCharSequence text, int color) {
    }

    private final boolean available = ClientPlayNetworking.canSend(AskPayload.TYPE);
    private EditBox input;
    private Button upButton;
    private Button downButton;
    private boolean showHistory;
    private List<Line> lines = List.of();
    private int scroll;

    AssistantScreen() {
        super(Component.translatable("screen.minecraft_ia.title"));
    }

    @Override
    protected void init() {
        int w = panelWidth();
        int x = (width - w) / 2;
        int y = height - 28;
        input = new EditBox(font, x, y, w - 112, 20, Component.translatable("screen.minecraft_ia.question"));
        input.setMaxLength(AskPayload.MAX_LENGTH);
        input.setHint(Component.translatable(available ? "screen.minecraft_ia.hint" : "screen.minecraft_ia.unavailable"));
        input.setEditable(available);
        addRenderableWidget(input);
        Button ask = addRenderableWidget(Button.builder(Component.translatable("screen.minecraft_ia.ask"), b -> submit())
                .bounds(x + w - 108, y, 52, 20).build());
        Button history = addRenderableWidget(Button.builder(Component.translatable("screen.minecraft_ia.history"), b -> toggleHistory())
                .bounds(x + w - 54, y, 54, 20).build());
        ask.active = available;
        history.active = available;
        upButton = addRenderableWidget(Button.builder(Component.literal("✔"), b -> vote(true)).bounds(x + w - 44, 6, 20, 20)
                .tooltip(Tooltip.create(Component.translatable("screen.minecraft_ia.vote_up"))).build());
        downButton = addRenderableWidget(Button.builder(Component.literal("✘"), b -> vote(false)).bounds(x + w - 22, 6, 20, 20)
                .tooltip(Tooltip.create(Component.translatable("screen.minecraft_ia.vote_down"))).build());
        setInitialFocus(input);
        ClientState.INSTANCE.listen(this::refresh);
        refresh();
    }

    @Override
    public void removed() {
        ClientState.INSTANCE.listen(() -> { });
    }

    private int panelWidth() {
        return Math.min(width - 40, MAX_WIDTH);
    }

    private int visibleLines() {
        return Math.max(1, (height - 40 - TOP) / (font.lineHeight + 1));
    }

    private void submit() {
        String question = input.getValue().strip();
        if (!available || question.isEmpty()) {
            return;
        }
        showHistory = false;
        ClientState.INSTANCE.asked(question);
        ClientPlayNetworking.send(new AskPayload(question));
        input.setValue("");
    }

    private void toggleHistory() {
        showHistory = !showHistory;
        if (showHistory) {
            ClientPlayNetworking.send(new HistoryRequestPayload(HISTORY_LIMIT));
        }
        refresh();
    }

    private void vote(boolean up) {
        ClientState.INSTANCE.latestVotable().ifPresent(entry -> {
            ClientPlayNetworking.send(new VotePayload(entry.reply.answerId(), up));
            ClientState.INSTANCE.voted(entry, up);
        });
    }

    private void refresh() {
        lines = showHistory ? historyLines() : conversationLines();
        boolean votable = !showHistory && ClientState.INSTANCE.latestVotable().isPresent();
        upButton.visible = votable;
        downButton.visible = votable;
        scroll = Math.max(0, lines.size() - visibleLines());
    }

    private List<Line> conversationLines() {
        List<Line> out = new ArrayList<>();
        List<ClientState.Entry> conversation = ClientState.INSTANCE.conversation();
        if (conversation.isEmpty()) {
            add(out, Component.translatable("screen.minecraft_ia.empty").getString(), GRAY);
        }
        for (ClientState.Entry entry : conversation) {
            String question = entry.question != null ? entry.question : Component.translatable("screen.minecraft_ia.retry").getString();
            add(out, "» " + question, YELLOW);
            if (entry.reply == null) {
                add(out, Component.translatable("screen.minecraft_ia.searching").getString(), GRAY);
            } else {
                add(out, entry.reply.text(), color(entry.reply.status()));
                if (!entry.reply.sources().isEmpty()) {
                    add(out, Component.translatable("screen.minecraft_ia.sources").getString()
                            + entry.reply.sources().stream().map(s -> SourceLabel.of(s).label()).collect(Collectors.joining(", ")), GRAY);
                }
                if (entry.vote != null) {
                    add(out, entry.vote ? "✔" : "✘", entry.vote ? WHITE : RED);
                }
            }
            add(out, "", WHITE);
        }
        return out;
    }

    private List<Line> historyLines() {
        List<Line> out = new ArrayList<>();
        List<HistoryItem> history = ClientState.INSTANCE.history();
        if (history.isEmpty()) {
            add(out, Component.translatable("screen.minecraft_ia.history_empty").getString(), GRAY);
        }
        for (HistoryItem item : history) {
            String vote = item.vote() == null ? "" : item.vote() ? "  ✔" : "  ✘";
            add(out, "» " + item.question() + vote, YELLOW);
            add(out, item.text(), color(item.status()));
            add(out, "", WHITE);
        }
        return out;
    }

    private void add(List<Line> out, String text, int color) {
        if (text.isEmpty()) {
            out.add(new Line(FormattedCharSequence.EMPTY, color));
            return;
        }
        font.split(Component.literal(text), panelWidth()).forEach(line -> out.add(new Line(line, color)));
    }

    private static int color(String status) {
        return switch (status) {
            case "ok" -> WHITE;
            case "unknown" -> YELLOW;
            default -> RED;
        };
    }

    @Override
    public boolean keyPressed(int keyCode, int scanCode, int modifiers) {
        if ((keyCode == GLFW.GLFW_KEY_ENTER || keyCode == GLFW.GLFW_KEY_KP_ENTER) && input.isFocused()) {
            submit();
            return true;
        }
        return super.keyPressed(keyCode, scanCode, modifiers);
    }

    @Override
    public boolean mouseScrolled(double mouseX, double mouseY, double scrollX, double scrollY) {
        int max = Math.max(0, lines.size() - visibleLines());
        scroll = Math.clamp(scroll - (int) Math.signum(scrollY) * 3, 0, max);
        return true;
    }

    @Override
    public void render(GuiGraphics graphics, int mouseX, int mouseY, float partialTick) {
        super.render(graphics, mouseX, mouseY, partialTick);
        int w = panelWidth();
        int x = (width - w) / 2;
        int bottom = height - 36;
        graphics.drawCenteredString(font, showHistory ? Component.translatable("screen.minecraft_ia.history") : title, width / 2, 12, WHITE);
        graphics.fill(x - 4, TOP - 4, x + w + 4, bottom + 2, 0x90000000);
        int step = font.lineHeight + 1;
        int end = Math.min(lines.size(), scroll + visibleLines());
        for (int i = scroll; i < end; i++) {
            Line line = lines.get(i);
            graphics.drawString(font, line.text(), x, TOP + (i - scroll) * step, line.color());
        }
    }

    @Override
    public boolean isPauseScreen() {
        return false;
    }
}
