package io.github.nistroy.minecraftia;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

class CraftingLayoutTest {
    @Test
    void shapedRecipeKeepsItsShape() {
        assertArrayEquals(new int[] {0, 1, 3, 4}, CraftingLayout.slots(2, 4).orElseThrow());
        assertArrayEquals(new int[] {0, 3}, CraftingLayout.slots(1, 2).orElseThrow());
        assertArrayEquals(new int[] {0, 1, 2, 3, 4, 5, 6, 7, 8}, CraftingLayout.slots(3, 9).orElseThrow());
    }

    @Test
    void shapelessFillsSmallestSquare() {
        assertEquals(1, CraftingLayout.shapelessColumns(1));
        assertEquals(2, CraftingLayout.shapelessColumns(4));
        assertEquals(3, CraftingLayout.shapelessColumns(5));
    }

    @Test
    void recipesBiggerThanTheGridAreRefused() {
        assertTrue(CraftingLayout.slots(4, 4).isEmpty());
        assertTrue(CraftingLayout.slots(3, 10).isEmpty());
        assertTrue(CraftingLayout.slots(0, 1).isEmpty());
    }
}
