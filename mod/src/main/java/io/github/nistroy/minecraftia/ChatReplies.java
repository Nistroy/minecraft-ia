package io.github.nistroy.minecraftia;

import java.util.List;
import net.minecraft.ChatFormatting;
import net.minecraft.network.chat.ClickEvent;
import net.minecraft.network.chat.Component;
import net.minecraft.network.chat.HoverEvent;
import net.minecraft.network.chat.MutableComponent;
import net.minecraft.server.level.ServerPlayer;

/** Réponses dans le chat, privées (message système au seul joueur), pour /ia et les joueurs sans mod client. */
final class ChatReplies {
    private static final int HISTORY_LINES = 5;

    private ChatReplies() {
    }

    static void pending(ServerPlayer player, String text) {
        player.sendSystemMessage(prefix().append(Component.literal(text).withStyle(ChatFormatting.GRAY, ChatFormatting.ITALIC)));
    }

    static void answer(ServerPlayer player, BrainReply reply) {
        MutableComponent message = prefix().append(Component.literal(ItemMarkers.strip(reply.text())).withStyle(color(reply.status())));
        if (!reply.sources().isEmpty()) {
            message.append(Component.literal("\nSources : ").withStyle(ChatFormatting.GRAY));
            List<String> sources = reply.sources();
            for (int i = 0; i < sources.size(); i++) {
                if (i > 0) {
                    message.append(Component.literal(", ").withStyle(ChatFormatting.GRAY));
                }
                message.append(source(SourceLabel.of(sources.get(i))));
            }
        }
        if (reply.hasAnswer()) {
            message.append("\n")
                    .append(button("[✔ juste]", "/ia vote " + reply.answerId() + " oui", ChatFormatting.GREEN, "Réponse juste"))
                    .append(" ")
                    .append(button("[✘ fausse]", "/ia vote " + reply.answerId() + " non", ChatFormatting.RED,
                            "Réponse fausse : je cherche encore"));
        }
        player.sendSystemMessage(message);
    }

    static void history(ServerPlayer player, List<HistoryItem> items) {
        if (items.isEmpty()) {
            player.sendSystemMessage(prefix().append(Component.literal("Historique vide ou indisponible.").withStyle(ChatFormatting.GRAY)));
            return;
        }
        MutableComponent message = prefix().append(Component.literal("Tes dernières questions :"));
        for (HistoryItem item : items.subList(0, Math.min(HISTORY_LINES, items.size()))) {
            String vote = item.vote() == null ? "" : item.vote() ? " ✔" : " ✘";
            message.append(Component.literal("\n• " + Texts.truncate(item.question(), 60)).withStyle(ChatFormatting.YELLOW))
                    .append(Component.literal(" → " + Texts.truncate(ItemMarkers.strip(item.text()), 100) + vote).withStyle(ChatFormatting.GRAY));
        }
        player.sendSystemMessage(message);
    }

    private static MutableComponent prefix() {
        return Component.literal("[IA] ").withStyle(ChatFormatting.AQUA);
    }

    private static ChatFormatting color(String status) {
        return switch (status) {
            case "ok" -> ChatFormatting.WHITE;
            case "unknown" -> ChatFormatting.YELLOW;
            default -> ChatFormatting.RED;
        };
    }

    private static MutableComponent source(SourceLabel label) {
        if (label.url() == null) {
            return Component.literal(label.label()).withStyle(ChatFormatting.GRAY);
        }
        return Component.literal(label.label()).withStyle(style -> style.withColor(ChatFormatting.BLUE).withUnderlined(true)
                .withClickEvent(new ClickEvent(ClickEvent.Action.OPEN_URL, label.url()))
                .withHoverEvent(new HoverEvent(HoverEvent.Action.SHOW_TEXT, Component.literal(label.url()))));
    }

    private static MutableComponent button(String text, String command, ChatFormatting color, String hover) {
        return Component.literal(text).withStyle(style -> style.withColor(color)
                .withClickEvent(new ClickEvent(ClickEvent.Action.RUN_COMMAND, command))
                .withHoverEvent(new HoverEvent(HoverEvent.Action.SHOW_TEXT, Component.literal(hover))));
    }
}
