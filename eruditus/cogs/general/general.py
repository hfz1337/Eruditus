from importlib import import_module
import os

import discord
from discord.ext import commands
from discord.ext.commands import Bot

from discord_slash import SlashContext, cog_ext
from discord_slash.utils.manage_commands import create_option

import pymongo

from cogs.general.help import cog_help

from config import (
    MONGODB_URI,
    DBNAME_PREFIX,
    CONFIG_COLLECTION,
    MINIMUM_PLAYER_COUNT,
    VOTING_STARTS_COUNTDOWN,
    VOTING_VERDICT_COUNTDOWN,
)

# MongoDB handle
mongo = pymongo.MongoClient(MONGODB_URI)


class General(commands.Cog):
    """This cog contains general commands."""

    def __init__(self, bot: Bot, extensions: list) -> None:
        self._bot = bot
        self._bot_extensions = extensions

    @cog_ext.cog_slash(
        name=cog_help["commands"]["help"]["name"],
        description=cog_help["commands"]["help"]["description"],
        options=[
            create_option(**option)
            for option in cog_help["commands"]["help"]["options"]
        ],
    )
    async def _help(self, ctx: SlashContext) -> None:
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
            .set_thumbnail(url=self._bot.user.avatar_url)
            .set_footer(
                text=(
                    "“I never desire to converse with a man who has written more than "
                    "he has read.”\n"
                    "― Samuel Johnson, Johnsonian Miscellanies - Vol II"
                )
            )
        )

        for extension in self._bot_extensions:
            if "commands" in self._bot_extensions[extension]:
                for command in self._bot_extensions[extension]["commands"]:
                    embed.add_field(
                        name=f"/{command}",
                        value=self._bot_extensions[extension]["commands"][command][
                            "description"
                        ],
                        inline=False,
                    )
            else:
                embed.add_field(
                    name=f"/{extension}",
                    value=self._bot_extensions[extension]["description"],
                    inline=False,
                )
        await ctx.send(embed=embed)

    @commands.has_permissions(manage_channels=True)
    @commands.guild_only()
    @cog_ext.cog_slash(
        name=cog_help["commands"]["config"]["name"],
        description=cog_help["commands"]["config"]["description"],
        options=[
            create_option(**option)
            for option in cog_help["commands"]["config"]["options"]
        ],
    )
    async def _config(
        self,
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


def setup(bot: Bot) -> None:
    extensions = {
        ext: import_module(f"cogs.{ext}.help").cog_help for ext in os.listdir("cogs")
    }
    bot.add_cog(General(bot, extensions))
