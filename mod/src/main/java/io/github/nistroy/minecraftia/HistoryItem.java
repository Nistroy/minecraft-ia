package io.github.nistroy.minecraftia;

/** Entrée d'historique ; vote null = pas encore voté. */
public record HistoryItem(int answerId, String question, String text, String status, Boolean vote) {
}
