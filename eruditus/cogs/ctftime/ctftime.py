from datetime import datetime
import time
import requests

import discord
from discord.ext import commands
from discord.ext.commands import Bot

from discord_slash import SlashContext, cog_ext
from discord_slash.utils.manage_commands import create_option

from pymongo import MongoClient

from cogs.ctftime.help import cog_help
from lib.ctftime import scrape_current_events
from config import (
    MONGODB_URI,
    DBNAME_PREFIX,
    CTFTIME_COLLECTION,
    CTFTIME_URL,
    USER_AGENT,
    DATE_FORMAT,
)

# MongoDB handle
mongo = MongoClient(MONGODB_URI)


class CTFTime(commands.Cog):
    """This cog provides information about ongoing/upcoming events, as well as a
    specific year's leaderboard.
    """

    def __init__(self, bot: Bot) -> None:
        self._bot = bot

    @cog_ext.cog_subcommand(
        base=cog_help["name"],
        name=cog_help["subcommands"]["current"]["name"],
        description=cog_help["subcommands"]["current"]["description"],
        options=[
            create_option(**option)
            for option in cog_help["subcommands"]["current"]["options"]
        ],
    )
    async def _current(self, ctx: SlashContext) -> None:
        """Show ongoing events.

        Args:
            ctx: The context in which the command is being invoked under.

        """
        await ctx.defer()
        no_running_events = True
        for event in scrape_current_events():
            # Convert timestamps to dates
            event["start"] = datetime.strftime(
                datetime.fromtimestamp(event["start"]), DATE_FORMAT
            )
            event["end"] = datetime.strftime(
                datetime.fromtimestamp(event["end"]), DATE_FORMAT
            )

            embed = (
                discord.Embed(
                    title=f"🔴 {event['name']} is live",
                    description=(
                        f"Event website: {event['website']}\n"
                        f"CTFtime URL: {CTFTIME_URL}/event/{event['id']}"
                    ),
                    color=discord.Colour.red(),
                )
                .set_thumbnail(url=event["logo"])
                .add_field(name="Description", value=event["description"], inline=False)
                .add_field(name="Prizes", value=event["prizes"], inline=False)
                .add_field(
                    name="Format",
                    value=f"{event['location']} {event['format']}",
                    inline=True,
                )
                .add_field(
                    name="Organizers",
                    value=", ".join(event["organizers"]),
                    inline=True,
                )
                .add_field(name="Weight", value=event["weight"], inline=True)
                .add_field(
                    name="Timeframe",
                    value=f"{event['start']}\n{event['end']}",
                    inline=False,
                )
            )

            no_running_events = False
            await ctx.send(embed=embed)

        if no_running_events:
            await ctx.send("No ongoing CTFs for the moment.")

    @cog_ext.cog_subcommand(
        base=cog_help["name"],
        name=cog_help["subcommands"]["upcoming"]["name"],
        description=cog_help["subcommands"]["upcoming"]["description"],
        options=[
            create_option(**option)
            for option in cog_help["subcommands"]["upcoming"]["options"]
        ],
    )
    async def _upcoming(self, ctx: SlashContext, limit: int = 3) -> None:
        """Shows upcoming events.

        Args:
            ctx: The context in which the command is being invoked under.
            limit: Number of events to show.

        """
        await ctx.defer()
        query_filter = {"start": {"$gt": int(time.time())}}
        no_upcoming_events = True

        events = list(
            mongo[f"{DBNAME_PREFIX}-{ctx.guild_id}"][CTFTIME_COLLECTION]
            .find(query_filter)
            .limit(limit)
        )

        # If we didn't update the database yet through the background task, we do it
        # manually
        if not events:
            await self._bot.get_cog("EventManager").update_events()
            events = (
                mongo[f"{DBNAME_PREFIX}-{ctx.guild_id}"][CTFTIME_COLLECTION]
                .find(query_filter)
                .limit(limit)
            )

        for event in events:
            # Convert timestamps to dates
            event["start"] = datetime.strftime(
                datetime.fromtimestamp(event["start"]), DATE_FORMAT
            )
            event["end"] = datetime.strftime(
                datetime.fromtimestamp(event["end"]), DATE_FORMAT
            )

            embed = (
                discord.Embed(
                    title=f"🆕 {event['name']}",
                    description=(
                        f"Event website: {event['website']}\n"
                        f"CTFtime URL: {CTFTIME_URL}/event/{event['id']}"
                    ),
                    color=discord.Colour.red(),
                )
                .set_thumbnail(url=event["logo"])
                .add_field(name="Description", value=event["description"], inline=False)
                .add_field(name="Prizes", value=event["prizes"], inline=False)
                .add_field(
                    name="Format",
                    value=f"{event['location']} {event['format']}",
                    inline=True,
                )
                .add_field(
                    name="Organizers",
                    value=", ".join(event["organizers"]),
                    inline=True,
                )
                .add_field(name="Weight", value=event["weight"], inline=True)
                .add_field(
                    name="Timeframe",
                    value=f"{event['start']}\n{event['end']}",
                    inline=False,
                )
            )

            no_upcoming_events = False
            await ctx.send(embed=embed)

        if no_upcoming_events:
            await ctx.send("No upcoming CTFs.")

    @cog_ext.cog_subcommand(
        base=cog_help["name"],
        name=cog_help["subcommands"]["top"]["name"],
        description=cog_help["subcommands"]["top"]["description"],
        options=[
            create_option(**option)
            for option in cog_help["subcommands"]["top"]["options"]
        ],
    )
    async def _top(self, ctx: SlashContext, year: int = None) -> None:
        """Shows a specific year's leaderboard

        Args:
            ctx: The context in which the command is being invoked under.
            year: The year to show the leaderboard for. Defaults to None, which means
                the current year.

        """
        await ctx.defer()
        year = year or datetime.today().year
        year = str(year)

        headers = {"User-Agent": USER_AGENT}
        response = requests.get(
            url=f"{CTFTIME_URL}/api/v1/top/{year}/", headers=headers
        )
        if response.status_code == 200 and year in response.json():
            teams = response.json()[year]
            leaderboard = f"{'[Rank]':<10}{'[Team]':<50}{'[Score]'}\n"

            for rank, team in enumerate(teams, start=1):
                score = round(team["points"], 4)
                leaderboard += f"{rank:<10}{team['team_name']:<50}{score}\n"

            await ctx.send(
                f":triangular_flag_on_post:  **{year} CTFtime Leaderboard**"
                f"```ini\n{leaderboard.strip()}```"
            )
        else:
            await ctx.send("No results.")


def setup(bot: Bot) -> None:
    """Adds the extension to the bot."""
    bot.add_cog(CTFTime(bot))
