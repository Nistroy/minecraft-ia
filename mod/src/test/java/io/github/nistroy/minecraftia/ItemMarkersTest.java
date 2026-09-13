package io.github.nistroy.minecraftia;

import static org.junit.jupiter.api.Assertions.assertEquals;

import io.github.nistroy.minecraftia.ItemMarkers.Icon;
import io.github.nistroy.minecraftia.ItemMarkers.Text;
import java.util.List;
import org.junit.jupiter.api.Test;

class ItemMarkersTest {
    @Test
    void parsesTextItemsAndTags() {
        assertEquals(List.of(new Text("4 planches "), new Icon("minecraft:planks", true), new Text(", établi "),
                        new Icon("minecraft:crafting_table", false)),
                ItemMarkers.parse("4 planches [[#minecraft:planks]], établi [[minecraft:crafting_table]]"));
    }

    @Test
    void plainAndEmptyText() {
        assertEquals(List.of(new Text("rien")), ItemMarkers.parse("rien"));
        assertEquals(List.of(), ItemMarkers.parse(""));
    }

    @Test
    void malformedMarkerStaysText() {
        assertEquals(List.of(new Text("a [[Pas:Valide]] b")), ItemMarkers.parse("a [[Pas:Valide]] b"));
    }

    @Test
    void stripRemovesMarkersAndTheirSpace() {
        assertEquals("4 planches, ok", ItemMarkers.strip("4 planches [[#minecraft:planks]], ok"));
    }
}
