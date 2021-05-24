#
#                               Eruditus - CTF helper Bot
# ======================================================================================
# Eruditus is aimed towards CTF teams who communicate via Discord during CTF
# competitions.
# ======================================================================================

from discord.ext.commands import Context, Bot, CommandError
from discord_slash import SlashCommand
from discord.ext import commands
from help import help_info
import traceback
import logging
import discord
import sys
import os

# Setup logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)
handler = logging.FileHandler(filename="eruditus.log", encoding="utf-8", mode="w")
handler.setFormatter(
    logging.Formatter("%(asctime)s:%(levelname)s:%(name)s: %(message)s")
)
logger.addHandler(handler)


bot = Bot(command_prefix="!", description="Eruditus - CTF helper bot")
bot.remove_command("help")

slash = SlashCommand(bot, sync_commands=True, sync_on_cog_reload=True)

extensions = [
    "ctf",
    "ctftime",
    "syscalls",
    "cipher",
    "encoding",
]


@bot.event
async def on_ready() -> None:
    logger.success(f"{bot.user} connected to {bot.guilds[0]}")
    await bot.change_presence(activity=discord.Game(name="!help"))


@bot.command(name="help")
async def help(ctx: Context, extension: str = None, command: str = None) -> None:
    # If the help command is called without arguments or the extension doesn't exist,
    # display the bot information with the available command groups.
    if extension not in extensions:
        embed = (
            discord.Embed(
                title="Eruditus - CTF helper bot",
                description=(
                    "Eruditus is aimed towards CTF teams who communicate via Discord "
                    "during CTF competitions."
                ),
                colour=discord.Colour.blue(),
            )
            .set_thumbnail(url=bot.user.avatar_url)
            .set_footer(
                text=(
                    "“I never desire to converse with a man who has written more than "
                    "he has read.”\n"
                    "― Samuel Johnson, Johnsonian Miscellanies - Vol II"
                )
            )
        )

        for extension in extensions:
            embed.add_field(
                name=f"{bot.command_prefix}help {extension}",
                value=f"Show help for **{extension}** commands",
                inline=False,
            )
    # If the help command is called with the extension only, display commands available
    # for that extension with a brief description for each subcommand.
    elif command is None:
        embed = discord.Embed(
            title=f"Commands group for {bot.command_prefix}{extension}",
            colour=discord.Colour.blue(),
        ).set_thumbnail(url=bot.user.avatar_url)

        for command in help_info[extension]:
            embed.add_field(
                name=help_info[extension][command]["usage"].format(bot.command_prefix),
                value=help_info[extension][command]["brief"],
                inline=False,
            )
    # If the help command is called with both the extension and the subcommand, display
    # thorough description of the latter.
    else:
        # If this is an alias, we fetch the original command
        if command not in help_info[extension]:
            for original_command in help_info[extension]:
                if command in help_info[extension][original_command]["aliases"]:
                    command = original_command
                    break
        embed = discord.Embed(
            title=help_info[extension][command]["usage"].format(bot.command_prefix),
            description=help_info[extension][command]["help"],
            colour=discord.Colour.blue(),
        ).set_thumbnail(url=bot.user.avatar_url)

    await ctx.channel.send(embed=embed)


@bot.event
async def on_command_error(ctx: Context, err: CommandError) -> None:
    if isinstance(err, commands.errors.CommandNotFound):
        pass
    elif isinstance(err, commands.errors.MissingRequiredArgument):
        await ctx.send(
            "Missing one or more required arguments.\n"
            f"Use `{bot.command_prefix}help {ctx.command}` for more information."
        )
    elif isinstance(err, commands.errors.BadArgument):
        await ctx.send(
            "Bad argument.\n"
            f"Use `{bot.command_prefix}help {ctx.command}` for more information."
        )
    elif isinstance(err, commands.errors.TooManyArguments):
        await ctx.send("Too many arguments were provided.")
    elif isinstance(err, commands.errors.MissingPermissions):
        await ctx.send("Permission denied.")
    elif isinstance(err, commands.errors.BotMissingPermissions):
        await ctx.send("I don't have enough privileges to perform this action :(")
    elif isinstance(err, commands.errors.NoPrivateMessage):
        await ctx.send("This command can't be used in DM.")
    else:
        await ctx.message.add_reaction("❌")
        traceback.print_exception(type(err), err, err.__traceback__, file=sys.stderr)


if __name__ == "__main__":
    for extension in extensions:
        bot.load_extension(f"cogs.{extension}")
        logger.info(f"Loaded extension: {extension}")
    bot.run(os.getenv("DISCORD_TOKEN"))
