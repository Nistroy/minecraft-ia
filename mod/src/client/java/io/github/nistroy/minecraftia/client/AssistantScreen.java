package io.github.nistroy.minecraftia.client;

import io.github.nistroy.minecraftia.net.AskPayload;
import io.github.nistroy.minecraftia.net.HistoryRequestPayload;
import io.github.nistroy.minecraftia.net.VotePayload;
import java.util.Optional;
import net.fabricmc.fabric.api.client.networking.v1.ClientPlayNetworking;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.client.gui.components.Button;
import net.minecraft.client.gui.components.EditBox;
import net.minecraft.client.gui.components.Tooltip;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.network.chat.Component;
import org.lwjgl.glfw.GLFW;

/** Écran de l'assistant : onglets conversation / historique, question, votes ✔/✘ sur la dernière réponse. */
final class AssistantScreen extends Screen {
    private static final int MAX_WIDTH = 420;
    private static final int MARGIN = 8;
    private static final int PAD = 6;
    private static final int HEADER = 28;
    private static final int FOOTER = 30;
    private static final int HISTORY_LIMIT = 20;
    private static final int FRAME_BG = 0xE0101014;
    private static final int FRAME_LINE = 0xFF4A4A5A;
    private static final int WHITE = 0xFFFFFFFF;

    private final boolean available = ClientPlayNetworking.canSend(AskPayload.TYPE);
    private final ItemIcons icons = new ItemIcons();
    private ConversationView view;
    private EditBox input;
    private Button conversationTab;
    private Button historyTab;
    private Button upButton;
    private Button downButton;
    private boolean showHistory;
    private int left;
    private int right;
    private int top;
    private int bottom;

    AssistantScreen() {
        super(Component.translatable("screen.minecraft_ia.title"));
    }

    @Override
    protected void init() {
        int panelWidth = Math.min(width - 2 * MARGIN, MAX_WIDTH);
        left = (width - panelWidth) / 2;
        right = left + panelWidth;
        top = MARGIN;
        bottom = height - MARGIN;
        int inner = right - PAD;
        int footerY = bottom - FOOTER + 5;

        input = addRenderableWidget(new EditBox(font, left + PAD, footerY, inner - 110 - (left + PAD), 20,
                Component.translatable("screen.minecraft_ia.question")));
        input.setMaxLength(AskPayload.MAX_LENGTH);
        input.setHint(Component.translatable(available ? "screen.minecraft_ia.hint" : "screen.minecraft_ia.unavailable"));
        input.setEditable(available);
        Button ask = addRenderableWidget(Button.builder(Component.translatable("screen.minecraft_ia.ask"), b -> submit())
                .bounds(inner - 106, footerY, 60, 20).build());
        ask.active = available;
        upButton = addRenderableWidget(Button.builder(Component.literal("✔"), b -> vote(true)).bounds(inner - 42, footerY, 20, 20)
                .tooltip(Tooltip.create(Component.translatable("screen.minecraft_ia.vote_up"))).build());
        downButton = addRenderableWidget(Button.builder(Component.literal("✘"), b -> vote(false)).bounds(inner - 20, footerY, 20, 20)
                .tooltip(Tooltip.create(Component.translatable("screen.minecraft_ia.vote_down"))).build());
        conversationTab = addRenderableWidget(Button.builder(Component.translatable("screen.minecraft_ia.conversation"),
                b -> show(false)).bounds(inner - 154, top + 4, 84, 20).build());
        historyTab = addRenderableWidget(Button.builder(Component.translatable("screen.minecraft_ia.history"),
                b -> show(true)).bounds(inner - 68, top + 4, 68, 20).build());

        view = new ConversationView(font, icons);
        view.setBounds(left + PAD, top + HEADER + 4, panelWidth - 2 * PAD, bottom - FOOTER - top - HEADER - 8);
        setInitialFocus(input);
        ClientState.INSTANCE.listen(this::refresh);
        refresh();
    }

    @Override
    public void removed() {
        ClientState.INSTANCE.listen(() -> { });
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

    private void show(boolean history) {
        showHistory = history;
        if (history) {
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
        conversationTab.active = showHistory;
        historyTab.active = available && !showHistory;
        if (showHistory) {
            view.showHistory(ClientState.INSTANCE.history());
        } else {
            view.showConversation(ClientState.INSTANCE.conversation(), this::craftingGrid);
        }
        boolean votable = !showHistory && ClientState.INSTANCE.latestVotable().isPresent();
        upButton.visible = votable;
        downButton.visible = votable;
    }

    private Optional<CraftingGrid> craftingGrid(String recipeId) {
        if (minecraft == null || minecraft.level == null) {
            return Optional.empty();
        }
        return CraftingGrid.of(minecraft.level.getRecipeManager(), minecraft.level.registryAccess(), recipeId);
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
        return view.mouseScrolled(scrollY);
    }

    /** Cadre dessiné ici : Screen.render dessine le fond puis les widgets par-dessus. */
    @Override
    public void renderBackground(GuiGraphics graphics, int mouseX, int mouseY, float partialTick) {
        super.renderBackground(graphics, mouseX, mouseY, partialTick);
        graphics.fill(left, top, right, bottom, FRAME_BG);
        graphics.renderOutline(left, top, right - left, bottom - top, FRAME_LINE);
        graphics.fill(left + 1, top + HEADER, right - 1, top + HEADER + 1, FRAME_LINE);
        graphics.fill(left + 1, bottom - FOOTER, right - 1, bottom - FOOTER + 1, FRAME_LINE);
    }

    @Override
    public void render(GuiGraphics graphics, int mouseX, int mouseY, float partialTick) {
        super.render(graphics, mouseX, mouseY, partialTick);
        graphics.drawString(font, title, left + PAD, top + 10, WHITE);
        view.render(graphics, mouseX, mouseY);
    }

    @Override
    public boolean isPauseScreen() {
        return false;
    }
}
