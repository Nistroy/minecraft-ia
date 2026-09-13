package io.github.nistroy.minecraftia.client;

import io.github.nistroy.minecraftia.CraftingLayout;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Optional;
import net.minecraft.client.gui.Font;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.core.HolderLookup;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.crafting.Ingredient;
import net.minecraft.world.item.crafting.Recipe;
import net.minecraft.world.item.crafting.RecipeManager;
import net.minecraft.world.item.crafting.ShapedRecipe;
import net.minecraft.world.item.crafting.ShapelessRecipe;

/** Grille 3x3 d'une recette de table de craft citée en source, lue dans les recettes que le serveur envoie au client. */
record CraftingGrid(List<List<ItemStack>> slots, ItemStack result) {
    static final int SLOT = 18;
    static final int HEIGHT = SLOT * CraftingLayout.SIZE;
    private static final int ARROW_WIDTH = 24;
    private static final int WIDTH = HEIGHT + ARROW_WIDTH + SLOT;
    private static final int SLOT_BG = 0xFF8B8B8B;
    private static final int SLOT_DARK = 0xFF373737;
    private static final int SLOT_LIGHT = 0xFFFFFFFF;
    private static final int ARROW = 0xFFC6C6C6;

    static Optional<CraftingGrid> of(RecipeManager recipes, HolderLookup.Provider registries, String recipeId) {
        ResourceLocation id = ResourceLocation.tryParse(recipeId);
        return id == null ? Optional.empty() : recipes.byKey(id).flatMap(holder -> build(holder.value(), registries));
    }

    private static Optional<CraftingGrid> build(Recipe<?> recipe, HolderLookup.Provider registries) {
        List<Ingredient> ingredients = recipe.getIngredients();
        int columns;
        if (recipe instanceof ShapedRecipe shaped) {
            columns = shaped.getWidth();
        } else if (recipe instanceof ShapelessRecipe) {
            columns = CraftingLayout.shapelessColumns(ingredients.size());
        } else {
            return Optional.empty(); // four, machines de mods : pas de grille, EMI les montre
        }
        return CraftingLayout.slots(columns, ingredients.size()).map(positions -> {
            List<List<ItemStack>> slots = new ArrayList<>(
                    Collections.nCopies(CraftingLayout.SIZE * CraftingLayout.SIZE, List.<ItemStack>of()));
            for (int i = 0; i < positions.length; i++) {
                slots.set(positions[i], List.of(ingredients.get(i).getItems()));
            }
            return new CraftingGrid(List.copyOf(slots), recipe.getResultItem(registries));
        });
    }

    /** Dessine grille, flèche et résultat ; renvoie l'item sous la souris (info-bulle) ou EMPTY. */
    ItemStack render(GuiGraphics graphics, Font font, int x, int y, int mouseX, int mouseY) {
        ItemStack hovered = ItemStack.EMPTY;
        for (int i = 0; i < slots.size(); i++) {
            int slotX = x + i % CraftingLayout.SIZE * SLOT;
            int slotY = y + i / CraftingLayout.SIZE * SLOT;
            hovered = slot(graphics, font, ItemIcons.cycle(slots.get(i)), slotX, slotY, mouseX, mouseY, hovered);
        }
        int arrowX = x + HEIGHT + 4;
        int middle = y + HEIGHT / 2;
        graphics.fill(arrowX, middle - 1, arrowX + 12, middle + 1, ARROW);
        graphics.fill(arrowX + 12, middle - 3, arrowX + 14, middle + 3, ARROW);
        graphics.fill(arrowX + 14, middle - 2, arrowX + 15, middle + 2, ARROW);
        graphics.fill(arrowX + 15, middle - 1, arrowX + 16, middle + 1, ARROW);
        return slot(graphics, font, result, x + WIDTH - SLOT, middle - SLOT / 2, mouseX, mouseY, hovered);
    }

    private static ItemStack slot(GuiGraphics graphics, Font font, ItemStack stack, int x, int y, int mouseX, int mouseY,
            ItemStack hovered) {
        graphics.fill(x, y, x + SLOT, y + SLOT, SLOT_BG);
        graphics.fill(x, y, x + SLOT - 1, y + 1, SLOT_DARK);
        graphics.fill(x, y, x + 1, y + SLOT - 1, SLOT_DARK);
        graphics.fill(x + 1, y + SLOT - 1, x + SLOT, y + SLOT, SLOT_LIGHT);
        graphics.fill(x + SLOT - 1, y + 1, x + SLOT, y + SLOT, SLOT_LIGHT);
        graphics.renderItem(stack, x + 1, y + 1);
        graphics.renderItemDecorations(font, stack, x + 1, y + 1);
        boolean over = mouseX >= x && mouseX < x + SLOT && mouseY >= y && mouseY < y + SLOT;
        return over && !stack.isEmpty() ? stack : hovered;
    }
}
