package io.github.nistroy.minecraftia.client;

import io.github.nistroy.minecraftia.ItemMarkers.Icon;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import net.minecraft.Util;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.core.registries.Registries;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.tags.TagKey;
import net.minecraft.world.item.ItemStack;

/** Items dessinés pour un marqueur, avec les modèles du jeu (vanilla + mods du pack) ; un tag fait défiler ses items. */
final class ItemIcons {
    private static final long CYCLE_MS = 1000;

    private final Map<Icon, List<ItemStack>> cache = new HashMap<>();

    /** Item à afficher maintenant ; EMPTY si l'id est inconnu du client (le nom reste écrit dans la phrase). */
    ItemStack current(Icon icon) {
        return cycle(cache.computeIfAbsent(icon, ItemIcons::resolve));
    }

    /** Rythme commun aux tags et aux ingrédients de recette. */
    static ItemStack cycle(List<ItemStack> stacks) {
        return stacks.isEmpty() ? ItemStack.EMPTY : stacks.get((int) (Util.getMillis() / CYCLE_MS % stacks.size()));
    }

    private static List<ItemStack> resolve(Icon icon) {
        ResourceLocation id = ResourceLocation.tryParse(icon.id());
        if (id == null) {
            return List.of();
        }
        if (icon.tag()) {
            return BuiltInRegistries.ITEM.getTag(TagKey.create(Registries.ITEM, id))
                    .map(tag -> tag.stream().map(holder -> holder.value().getDefaultInstance()).filter(s -> !s.isEmpty()).toList())
                    .orElse(List.of());
        }
        return BuiltInRegistries.ITEM.getOptional(id).map(item -> item.getDefaultInstance()).filter(s -> !s.isEmpty())
                .map(List::of).orElse(List.of());
    }
}
