from importlib import import_module
import traceback
import logging
import sys
import os

import discord
from discord.ext import commands
from discord.ext.commands import Bot, CommandError

from discord_slash import SlashCommand, SlashContext

import pymongo

from config import (
    MONGODB_URI,
    DBNAME,
    CONFIG_COLLECTION,
    MINIMUM_PLAYER_COUNT,
    VOTING_STARTS_COUNTDOWN,
    VOTING_VERDICT_COUNTDOWN,
    ARCHIVE_CATEGORY_CHANNEL,
    ANNOUNCEMENT_CHANNEL,
)

# Setup logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)
handler = logging.FileHandler(
    filename="/var/log/eruditus.log", encoding="utf-8", mode="w"
)
handler.setFormatter(
    logging.Formatter("%(asctime)s:%(levelname)s:%(name)s: %(message)s")
)
logger.addHandler(handler)

# Init config collection
mongo = pymongo.MongoClient(MONGODB_URI)[DBNAME]
if not mongo[CONFIG_COLLECTION].find_one():
    mongo[CONFIG_COLLECTION].insert_one(
        {
            "voting_verdict_countdown": VOTING_VERDICT_COUNTDOWN,
            "voting_starts_countdown": VOTING_STARTS_COUNTDOWN,
            "minimum_player_count": MINIMUM_PLAYER_COUNT,
            "archive_category_channel": ARCHIVE_CATEGORY_CHANNEL,
            "announcement_channel": ANNOUNCEMENT_CHANNEL,
        }
    )


bot = Bot(command_prefix="!", description="Eruditus - CTF helper bot")
bot.remove_command("help")

slash = SlashCommand(bot, sync_commands=True, sync_on_cog_reload=True)

extensions = {
    ext: import_module(f"cogs.{ext}.help").cog_help for ext in os.listdir("cogs")
}
tasks = [task.split(".")[0] for task in os.listdir("tasks") if task.endswith(".py")]


@bot.event
async def on_ready() -> None:
    logger.info(f"{bot.user} connected to {bot.guilds[0]}")
    await bot.change_presence(activity=discord.Game(name="/help"))


@slash.slash(name="help", description="Get help about the bot usage")
async def help_command(ctx: SlashContext) -> None:
    embed = (
        discord.Embed(
            title="Eruditus - CTF helper bot",
            url="https://github.com/hfz1337/Eruditus",
            description=(
                "Eruditus is dedicated to CTF teams who communicate via Discord "
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
            name=f"/{extension}",
            value=extensions[extension]["description"],
            inline=False,
        )
    await ctx.send(embed=embed)


@bot.event
async def on_command_error(ctx: SlashContext, err: CommandError) -> None:
    if isinstance(err, commands.errors.CommandNotFound):
        pass
    elif isinstance(err, commands.errors.MissingPermissions):
        await ctx.send("Permission denied.")
    elif isinstance(err, commands.errors.BotMissingPermissions):
        await ctx.send("I don't have enough privileges to perform this action :(")
    elif isinstance(err, commands.errors.NoPrivateMessage):
        await ctx.send("This command can't be used in DM.")
    else:
        await ctx.send("❌ An error has occured")
        traceback.print_exception(type(err), err, err.__traceback__, file=sys.stderr)


if __name__ == "__main__":
    for task in tasks:
        bot.load_extension(f"tasks.{task}")
        logger.info(f"Loaded task: {task}")
    for ext in extensions:
        bot.load_extension(f"cogs.{ext}.{ext}")
        logger.info(f"Loaded extension: {ext}")

    bot.run(os.getenv("DISCORD_TOKEN"))
