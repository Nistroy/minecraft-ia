package io.github.nistroy.minecraftia;

import static org.junit.jupiter.api.Assertions.assertEquals;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import java.util.List;
import org.junit.jupiter.api.Test;

class LiveSnapshotTest {
    @Test
    void tpsIsCappedByTickRate() {
        assertEquals(20.0, LiveSnapshot.tps(20f, 10_000_000L));
        assertEquals(12.5, LiveSnapshot.tps(20f, 80_000_000L));
        assertEquals(20.0, LiveSnapshot.tps(20f, 0L));
        assertEquals(12.3, LiveSnapshot.mspt(12_345_678L));
    }

    @Test
    void jsonMatchesBrainFormat() {
        LiveSnapshot snap = new LiveSnapshot(1000L, 19.8, 12.3,
                List.of(new LiveSnapshot.PlayerPos("Steve", "minecraft:overworld", 1, 64, -3)));
        JsonObject json = JsonParser.parseString(snap.toJson()).getAsJsonObject();
        assertEquals(1000L, json.get("updated").getAsLong());
        assertEquals(19.8, json.get("tps").getAsDouble());
        JsonObject player = json.getAsJsonArray("players").get(0).getAsJsonObject();
        assertEquals("Steve", player.get("name").getAsString());
        assertEquals("minecraft:overworld", player.get("dimension").getAsString());
        assertEquals(-3, player.get("z").getAsInt());
    }
}
