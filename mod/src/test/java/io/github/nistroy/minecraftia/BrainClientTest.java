package io.github.nistroy.minecraftia;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;
import java.io.IOException;
import java.io.UncheckedIOException;
import java.net.InetSocketAddress;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class BrainClientTest {
    private static final UUID PLAYER = UUID.fromString("0f1e2d3c-0000-0000-0000-000000000001");

    private HttpServer server;
    private final Map<String, String> requests = new ConcurrentHashMap<>();
    private final Map<String, String> auth = new ConcurrentHashMap<>();
    private BrainClient client;

    @BeforeEach
    void start() throws IOException {
        server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        route("/ask", 200, "{\"id\": 7, \"text\": \"Réponse\", \"sources\": [\"kb:mods/aether.md\"], \"status\": \"ok\"}");
        route("/vote", 200, "{\"ok\": true, \"retry\": {\"id\": 8, \"text\": \"Relance\", \"sources\": [], \"status\": \"unknown\"}}");
        route("/history", 200, "{\"items\": [{\"id\": 7, \"question\": \"q\", \"text\": \"r\", \"sources\": [],"
                + " \"status\": \"ok\", \"vote\": null, \"at\": \"2026-09-12T12:00:00+00:00\"}]}");
        server.start();
        client = new BrainClient(base(), () -> "tok", Duration.ofSeconds(5));
    }

    @AfterEach
    void stop() {
        server.stop(0);
    }

    @Test
    void askSendsAuthAndParsesReply() throws Exception {
        BrainReply reply = client.ask(PLAYER, "Steve", "portail « aether » ?").get(5, TimeUnit.SECONDS);
        assertEquals(new BrainReply(7, "ok", "Réponse", List.of("kb:mods/aether.md")), reply);
        assertEquals("Bearer tok", auth.get("/ask"));
        JsonObject body = JsonParser.parseString(requests.get("/ask")).getAsJsonObject();
        assertEquals(PLAYER.toString(), body.get("player").getAsString());
        assertEquals("Steve", body.get("name").getAsString());
        assertEquals("portail « aether » ?", body.get("question").getAsString());
    }

    @Test
    void voteReturnsRetry() throws Exception {
        Optional<BrainReply> retry = client.vote(PLAYER, 7, false).get(5, TimeUnit.SECONDS);
        assertEquals(8, retry.orElseThrow().answerId());
        JsonObject body = JsonParser.parseString(requests.get("/vote")).getAsJsonObject();
        assertEquals(7, body.get("id").getAsInt());
        assertEquals(false, body.get("up").getAsBoolean());
    }

    @Test
    void historyParsesNullVote() throws Exception {
        List<HistoryItem> items = client.history(PLAYER, 10).get(5, TimeUnit.SECONDS);
        assertEquals(1, items.size());
        assertEquals(7, items.get(0).answerId());
        assertNull(items.get(0).vote());
    }

    @Test
    void serverErrorBecomesErrorReply() throws Exception {
        server.removeContext("/ask");
        route("/ask", 500, "{\"error\": \"internal\"}");
        BrainReply reply = client.ask(PLAYER, "Steve", "q").get(5, TimeUnit.SECONDS);
        assertEquals("error", reply.status());
    }

    @Test
    void unreachableBrainAndMissingTokenBecomeErrorReplies() throws Exception {
        BrainClient down = new BrainClient(URI.create("http://127.0.0.1:1"), () -> "tok", Duration.ofSeconds(2));
        assertEquals("error", down.ask(PLAYER, "Steve", "q").get(5, TimeUnit.SECONDS).status());
        BrainClient noToken = new BrainClient(base(), () -> {
            throw new UncheckedIOException(new IOException("absent"));
        }, Duration.ofSeconds(2));
        assertEquals("error", noToken.ask(PLAYER, "Steve", "q").get(5, TimeUnit.SECONDS).status());
        assertTrue(noToken.history(PLAYER, 5).get(5, TimeUnit.SECONDS).isEmpty());
        assertTrue(!requests.containsKey("/history"));
    }

    private URI base() {
        return URI.create("http://127.0.0.1:" + server.getAddress().getPort());
    }

    private void route(String path, int status, String response) {
        server.createContext(path, exchange -> respond(exchange, path, status, response));
    }

    private void respond(HttpExchange exchange, String path, int status, String response) throws IOException {
        requests.put(path, new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8));
        auth.put(path, String.valueOf(exchange.getRequestHeaders().getFirst("Authorization")));
        byte[] bytes = response.getBytes(StandardCharsets.UTF_8);
        exchange.getResponseHeaders().add("Content-Type", "application/json; charset=utf-8");
        exchange.sendResponseHeaders(status, bytes.length);
        exchange.getResponseBody().write(bytes);
        exchange.close();
    }
}
