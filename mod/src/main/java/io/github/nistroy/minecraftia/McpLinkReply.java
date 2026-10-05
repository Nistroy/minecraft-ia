package io.github.nistroy.minecraftia;

/** Lien MCP donné par le cerveau, ou message d'erreur pour le joueur (error non vide). */
public record McpLinkReply(String url, String token, String error) {
    public static McpLinkReply failed(String error) {
        return new McpLinkReply("", "", error);
    }
}
