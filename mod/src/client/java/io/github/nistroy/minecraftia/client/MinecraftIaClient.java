package io.github.nistroy.minecraftia.client;

import com.mojang.blaze3d.platform.InputConstants;
import io.github.nistroy.minecraftia.net.AnswerPayload;
import io.github.nistroy.minecraftia.net.HistoryPayload;
import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientTickEvents;
import net.fabricmc.fabric.api.client.keybinding.v1.KeyBindingHelper;
import net.fabricmc.fabric.api.client.networking.v1.ClientPlayNetworking;
import net.minecraft.client.KeyMapping;
import org.lwjgl.glfw.GLFW;

public final class MinecraftIaClient implements ClientModInitializer {
    @Override
    public void onInitializeClient() {
        // Touche par défaut définie ici : options.txt du pack est en « preserve », jamais poussé aux joueurs.
        KeyMapping open = KeyBindingHelper.registerKeyBinding(new KeyMapping(
                "key.minecraft_ia.open", InputConstants.Type.KEYSYM, GLFW.GLFW_KEY_I, "key.categories.minecraft_ia"));
        ClientTickEvents.END_CLIENT_TICK.register(client -> {
            while (open.consumeClick()) {
                if (client.player != null && client.screen == null) {
                    client.setScreen(new AssistantScreen());
                }
            }
        });
        ClientPlayNetworking.registerGlobalReceiver(AnswerPayload.TYPE,
                (payload, context) -> ClientState.INSTANCE.onAnswer(payload.toReply()));
        ClientPlayNetworking.registerGlobalReceiver(HistoryPayload.TYPE,
                (payload, context) -> ClientState.INSTANCE.onHistory(payload.items()));
    }
}
