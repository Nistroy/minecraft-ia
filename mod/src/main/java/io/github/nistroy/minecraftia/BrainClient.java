package io.github.nistroy.minecraftia;

import static java.nio.charset.StandardCharsets.UTF_8;

import com.google.gson.Gson;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.function.Supplier;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Client HTTP asynchrone du cerveau (127.0.0.1). Ne bloque jamais le thread serveur ;
 * toute erreur (réseau, HTTP, JSON, jeton) devient une réponse d'erreur, jamais une exception.
 */
public final class BrainClient {
    public static final String UNAVAILABLE = "Cerveau IA injoignable, réessaie plus tard.";
    private static final Logger LOG = LoggerFactory.getLogger("minecraft_ia");
    private static final Gson GSON = new Gson();

    private final URI base;
    private final Supplier<String> token;
    private final Duration timeout;
    private final HttpClient http;

    public BrainClient(URI base, Supplier<String> token, Duration timeout) {
        this.base = base;
        this.token = token;
        this.timeout = timeout;
        this.http = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(5)).build();
    }

    public CompletableFuture<BrainReply> ask(UUID player, String name, String question) {
        JsonObject body = new JsonObject();
        body.addProperty("player", player.toString());
        body.addProperty("name", name);
        body.addProperty("question", question);
        return post("/ask", body).thenApply(json -> json.map(BrainClient::parseReply)
                .orElseGet(() -> BrainReply.error(UNAVAILABLE)));
    }

    /** Vote ; présent si le cerveau a relancé une recherche (ou en cas d'erreur, à afficher). */
    public CompletableFuture<Optional<BrainReply>> vote(UUID player, int answerId, boolean up) {
        JsonObject body = new JsonObject();
        body.addProperty("player", player.toString());
        body.addProperty("id", answerId);
        body.addProperty("up", up);
        return post("/vote", body).thenApply(json -> json
                .map(j -> j.get("retry") instanceof JsonObject retry ? Optional.of(parseReply(retry)) : Optional.<BrainReply>empty())
                .orElseGet(() -> Optional.of(BrainReply.error(UNAVAILABLE))));
    }

    public CompletableFuture<List<HistoryItem>> history(UUID player, int limit) {
        JsonObject body = new JsonObject();
        body.addProperty("player", player.toString());
        body.addProperty("limit", limit);
        return post("/history", body).thenApply(json -> json.map(BrainClient::parseHistory).orElseGet(List::of));
    }

    private CompletableFuture<Optional<JsonObject>> post(String path, JsonObject body) {
        String authorization;
        try {
            authorization = "Bearer " + token.get();
        } catch (RuntimeException e) {
            LOG.error("jeton du cerveau illisible : {}", e.getMessage());
            return CompletableFuture.completedFuture(Optional.empty());
        }
        HttpRequest request = HttpRequest.newBuilder(base.resolve(path))
                .timeout(timeout)
                .header("Authorization", authorization)
                .header("Content-Type", "application/json; charset=utf-8")
                .POST(HttpRequest.BodyPublishers.ofString(GSON.toJson(body), UTF_8))
                .build();
        return http.sendAsync(request, HttpResponse.BodyHandlers.ofString(UTF_8)).handle((response, error) -> {
            if (error != null) {
                LOG.warn("cerveau injoignable sur {} : {}", path, error.toString());
                return Optional.empty();
            }
            if (response.statusCode() != 200) {
                LOG.warn("cerveau : HTTP {} sur {}", response.statusCode(), path);
                return Optional.empty();
            }
            try {
                return Optional.of(JsonParser.parseString(response.body()).getAsJsonObject());
            } catch (RuntimeException e) {
                LOG.warn("cerveau : JSON invalide sur {}", path);
                return Optional.empty();
            }
        });
    }

    static BrainReply parseReply(JsonObject json) {
        JsonElement id = json.get("id");
        int answerId = id != null && !id.isJsonNull() ? id.getAsInt() : -1;
        return new BrainReply(answerId, string(json, "status", "error"), string(json, "text", ""), strings(json, "sources"));
    }

    private static List<HistoryItem> parseHistory(JsonObject json) {
        List<HistoryItem> items = new ArrayList<>();
        if (json.get("items") instanceof com.google.gson.JsonArray array) {
            for (JsonElement element : array) {
                JsonObject item = element.getAsJsonObject();
                JsonElement vote = item.get("vote");
                items.add(new HistoryItem(item.get("id").getAsInt(), string(item, "question", ""), string(item, "text", ""),
                        string(item, "status", ""), vote == null || vote.isJsonNull() ? null : vote.getAsBoolean()));
            }
        }
        return items;
    }

    private static String string(JsonObject json, String key, String fallback) {
        JsonElement value = json.get(key);
        return value != null && value.isJsonPrimitive() ? value.getAsString() : fallback;
    }

    private static List<String> strings(JsonObject json, String key) {
        List<String> out = new ArrayList<>();
        if (json.get(key) instanceof com.google.gson.JsonArray array) {
            array.forEach(e -> out.add(e.getAsString()));
        }
        return out;
    }
}
