package io.github.nistroy.minecraftia;

import java.util.Optional;

/** Place les ingrédients d'une recette de table de craft dans la grille 3x3 (case = ligne * 3 + colonne). */
public final class CraftingLayout {
    public static final int SIZE = 3;

    private CraftingLayout() {
    }

    /** Ingrédients rangés ligne par ligne sur `columns` colonnes ; vide si ça ne tient pas en 3x3. */
    public static Optional<int[]> slots(int columns, int count) {
        if (columns < 1 || columns > SIZE || count > SIZE * SIZE || (count + columns - 1) / columns > SIZE) {
            return Optional.empty();
        }
        int[] slots = new int[count];
        for (int i = 0; i < count; i++) {
            slots[i] = i / columns * SIZE + i % columns;
        }
        return Optional.of(slots);
    }

    /** Recette sans forme : plus petit carré qui contient tous les ingrédients. */
    public static int shapelessColumns(int count) {
        return count <= 1 ? 1 : count <= 4 ? 2 : SIZE;
    }
}
