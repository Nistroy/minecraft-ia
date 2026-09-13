package io.github.nistroy.minecraftia;

import com.mojang.brigadier.CommandDispatcher;
import com.mojang.brigadier.arguments.IntegerArgumentType;
import com.mojang.brigadier.arguments.StringArgumentType;
import com.mojang.brigadier.context.CommandContext;
import com.mojang.brigadier.exceptions.CommandSyntaxException;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;

/** /ia &lt;question&gt; · /ia historique · /ia vote &lt;id&gt; oui|non (boutons cliquables du chat). Joueurs seulement. */
final class IaCommand {
    private static final int CHAT_HISTORY = 5;

    private IaCommand() {
    }

    static void register(CommandDispatcher<CommandSourceStack> dispatcher, Gateway gateway) {
        dispatcher.register(Commands.literal("ia")
                .then(Commands.literal("historique").executes(ctx -> {
                    gateway.history(ctx.getSource().getPlayerOrException(), CHAT_HISTORY, Gateway.Channel.CHAT);
                    return 1;
                }))
                .then(Commands.literal("vote").then(Commands.argument("id", IntegerArgumentType.integer(1))
                        .then(Commands.literal("oui").executes(ctx -> vote(ctx, gateway, true)))
                        .then(Commands.literal("non").executes(ctx -> vote(ctx, gateway, false)))))
                .then(Commands.argument("question", StringArgumentType.greedyString()).executes(ctx -> {
                    gateway.ask(ctx.getSource().getPlayerOrException(), StringArgumentType.getString(ctx, "question"),
                            Gateway.Channel.CHAT);
                    return 1;
                })));
    }

    private static int vote(CommandContext<CommandSourceStack> ctx, Gateway gateway, boolean up) throws CommandSyntaxException {
        gateway.vote(ctx.getSource().getPlayerOrException(), IntegerArgumentType.getInteger(ctx, "id"), up, Gateway.Channel.CHAT);
        return 1;
    }
}
