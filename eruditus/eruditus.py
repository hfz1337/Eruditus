from importlib import import_module
import traceback
import logging
import sys
import os

import discord
from discord import Guild
from discord.ext import commands
from discord.ext.commands import Bot, CommandError

from discord_slash import SlashCommand, SlashContext
from discord_slash.model import SlashCommandOptionType as OptionType
from discord_slash.utils.manage_commands import create_option

import pymongo

from config import (
    MONGODB_URI,
    DBNAME_PREFIX,
    CONFIG_COLLECTION,
    MINIMUM_PLAYER_COUNT,
    VOTING_STARTS_COUNTDOWN,
    VOTING_VERDICT_COUNTDOWN,
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

# MongoDB handle
mongo = pymongo.MongoClient(MONGODB_URI)

bot = Bot(command_prefix=None, description="Eruditus - CTF helper bot")
slash = SlashCommand(bot, sync_commands=True, sync_on_cog_reload=True)

extensions = {
    ext: import_module(f"cogs.{ext}.help").cog_help for ext in os.listdir("cogs")
}
tasks = [task.split(".")[0] for task in os.listdir("tasks") if task.endswith(".py")]


async def setup_database(guild: Guild) -> None:
    """Sets up a database for a guild."""
    # Create an announcements channel
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(
            send_messages=False, add_reactions=False
        )
    }
    announcement_channel = await guild.create_text_channel(
        name="📢 Event Announcements",
        overwrites=overwrites,
    )

    # Create CTF archive category channel
    overwrites = {guild.default_role: discord.PermissionOverwrite(send_messages=False)}
    archive_category_channel = await guild.create_category(
        name="📁 CTF Archive",
        overwrites=overwrites,
    )

    # Insert the config document into the config collection of that guild's own db
    mongo[f"{DBNAME_PREFIX}-{guild.id}"][CONFIG_COLLECTION].insert_one(
        {
            "voting_verdict_countdown": VOTING_VERDICT_COUNTDOWN,
            "voting_starts_countdown": VOTING_STARTS_COUNTDOWN,
            "minimum_player_count": MINIMUM_PLAYER_COUNT,
            "archive_category_channel": archive_category_channel.id,
            "announcement_channel": announcement_channel.id,
        }
    )


@bot.event
async def on_ready() -> None:
    for guild in bot.guilds:
        # Setup guild database if it wasn't already
        if not mongo[f"{DBNAME_PREFIX}-{guild.id}"][CONFIG_COLLECTION].find_one():
            await setup_database(guild)
        logger.info(f"{bot.user} connected to {guild}")
    await bot.change_presence(activity=discord.Game(name="/help"))


@bot.event
async def on_guild_join(guild: Guild) -> None:
    """Sets up a database for the newly joined guild."""
    await setup_database(guild)
    logger.info(f"{bot.user} joined {guild}!")


@bot.event
async def on_guild_remove(guild: Guild) -> None:
    """Deletes the database for the guild we just left."""
    mongo.drop_database(f"{DBNAME_PREFIX}-{guild.id}")
    logger.info(f"{bot.user} left {guild}.")


@slash.slash(name="help", description="Get help about the bot usage")
async def help_command(ctx: SlashContext) -> None:
    """Shows help about the bot usage."""
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


@commands.has_permissions(manage_channels=True)
@slash.slash(
    name="config",
    description="Change configuration variables",
    options=[
        create_option(
            name="minimum_player_count",
            description=(
                "The minimum number of players required to create a CTF automatically"
            ),
            option_type=OptionType.INTEGER,
            required=False,
        ),
        create_option(
            name="voting_starts_countdown",
            description=(
                "The number of seconds remaining for a CTF to start when we announce "
                "it for voting"
            ),
            option_type=OptionType.INTEGER,
            required=False,
        ),
        create_option(
            name="voting_verdict_countdown",
            description=(
                "The number of seconds before the CTF starts from which we start "
                "considering the votes"
            ),
            option_type=OptionType.INTEGER,
            required=False,
        ),
    ],
)
async def config(
    ctx: SlashContext,
    minimum_player_count: int = None,
    voting_starts_countdown: int = None,
    voting_verdict_countdown: int = None,
) -> None:
    """Changes the guild's configuration."""
    # Get guild config from the database
    config = mongo[f"{DBNAME_PREFIX}-{ctx.guild.id}"][CONFIG_COLLECTION].find_one()

    if (
        minimum_player_count is None
        and voting_starts_countdown is None
        and voting_verdict_countdown is None
    ):
        current_configuration = "\n".join(
            f"{var}: {config[var]}"
            for var in [
                "minimum_player_count",
                "voting_starts_countdown",
                "voting_verdict_countdown",
            ]
        )
        await ctx.send(
            f"⚙️ Current configuration\n```yaml\n{current_configuration}\n```"
        )
        return

    minimum_player_count = minimum_player_count or MINIMUM_PLAYER_COUNT
    voting_starts_countdown = voting_starts_countdown or VOTING_STARTS_COUNTDOWN
    voting_verdict_countdown = voting_verdict_countdown or VOTING_VERDICT_COUNTDOWN

    mongo[f"{DBNAME_PREFIX}-{ctx.guild.id}"][CONFIG_COLLECTION].update_one(
        {"_id": config["_id"]},
        {
            "$set": {
                "minimum_player_count": minimum_player_count,
                "voting_starts_countdown": voting_starts_countdown,
                "voting_verdict_countdown": voting_verdict_countdown,
            }
        },
    )
    await ctx.send("⚙️ Configuration updated")


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
