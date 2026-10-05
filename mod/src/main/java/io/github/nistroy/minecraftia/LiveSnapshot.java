package io.github.nistroy.minecraftia;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import java.util.List;

/** Instantané live lu par le cerveau (`live_status_file`) : TPS, MSPT, position de chaque joueur. */
public record LiveSnapshot(long updated, double tps, double mspt, List<PlayerPos> players) {
    public record PlayerPos(String name, String dimension, int x, int y, int z) {
    }

    public LiveSnapshot {
        players = List.copyOf(players);
    }

    /** TPS réel : plafonné par la cadence visée (20, ou celle de /tick). */
    public static double tps(float tickRate, long averageTickNanos) {
        double tps = averageTickNanos > 0 ? Math.min(tickRate, 1e9 / averageTickNanos) : tickRate;
        return Math.round(tps * 10) / 10.0;
    }

    public static double mspt(long averageTickNanos) {
        return Math.round(averageTickNanos / 1e5) / 10.0;
    }

    public String toJson() {
        JsonObject json = new JsonObject();
        json.addProperty("updated", updated);
        json.addProperty("tps", tps);
        json.addProperty("mspt", mspt);
        JsonArray list = new JsonArray();
        for (PlayerPos p : players) {
            JsonObject player = new JsonObject();
            player.addProperty("name", p.name());
            player.addProperty("dimension", p.dimension());
            player.addProperty("x", p.x());
            player.addProperty("y", p.y());
            player.addProperty("z", p.z());
            list.add(player);
        }
        json.add("players", list);
        return json.toString();
    }
}
