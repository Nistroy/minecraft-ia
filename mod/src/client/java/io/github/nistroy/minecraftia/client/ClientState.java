package io.github.nistroy.minecraftia.client;

import io.github.nistroy.minecraftia.BrainReply;
import io.github.nistroy.minecraftia.HistoryItem;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

/** Conversation de la session (thread client uniquement). L'historique durable est côté cerveau. */
final class ClientState {
    static final ClientState INSTANCE = new ClientState();

    static final class Entry {
        final String question;
        BrainReply reply;
        Boolean vote;

        Entry(String question) {
            this.question = question;
        }
    }

    private final List<Entry> conversation = new ArrayList<>();
    private List<HistoryItem> history = List.of();
    private Runnable listener = () -> { };

    private ClientState() {
    }

    List<Entry> conversation() {
        return conversation;
    }

    List<HistoryItem> history() {
        return history;
    }

    void listen(Runnable listener) {
        this.listener = listener;
    }

    void asked(String question) {
        conversation.add(new Entry(question));
        listener.run();
    }

    /** Le serveur envoie exactement une réponse par question ou vote ✘ : elle remplit l'entrée en attente. */
    void onAnswer(BrainReply reply) {
        Entry pending = conversation.stream().filter(e -> e.reply == null).findFirst().orElse(null);
        if (pending == null) {
            pending = new Entry(null);
            conversation.add(pending);
        }
        pending.reply = reply;
        listener.run();
    }

    void onHistory(List<HistoryItem> items) {
        history = List.copyOf(items);
        listener.run();
    }

    Optional<Entry> latestVotable() {
        if (conversation.isEmpty()) {
            return Optional.empty();
        }
        Entry last = conversation.get(conversation.size() - 1);
        return last.reply != null && last.reply.hasAnswer() && last.vote == null ? Optional.of(last) : Optional.empty();
    }

    void voted(Entry entry, boolean up) {
        entry.vote = up;
        if (!up) {
            conversation.add(new Entry(null));
        }
        listener.run();
    }
}
