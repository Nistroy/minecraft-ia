package io.github.nistroy.minecraftia.cli;

import java.util.regex.Pattern;

/** Lien MCP du joueur, donné par le serveur. Forme stricte : il finit en argument ou en config d'une CLI. */
public record McpLink(String url, String token) {
    private static final Pattern URL = Pattern.compile("^https://[a-z0-9.-]+/mcp$");
    private static final Pattern TOKEN = Pattern.compile("^[A-Za-z0-9_-]{32,128}$");

    public McpLink {
        if (url == null || !URL.matcher(url).matches()) {
            throw new IllegalArgumentException("URL MCP inattendue");
        }
        if (token == null || !TOKEN.matcher(token).matches()) {
            throw new IllegalArgumentException("jeton MCP inattendu");
        }
    }
}
