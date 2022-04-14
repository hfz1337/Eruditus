from datetime import datetime
import time
import aiohttp

from discord import app_commands
import discord

from lib.ctftime import scrape_current_events, scrape_event_info

from typing import Optional

from config import (
    CTFTIME_URL,
    USER_AGENT,
)


class CTFTime(app_commands.Group):
    """A command group that provides information about ongoing/upcoming events, as well
    as a specific year's leaderboard.
    """

    def __init__(self):
        super().__init__(name="ctftime")

    @app_commands.command()
    async def current(self, interaction: discord.Interaction) -> None:
        """Show ongoing CTF competitions.

        Args:
            interaction: The interaction that triggered this command.
        """
        await interaction.response.defer()

        no_running_events = True
        async for event_info in scrape_current_events():
            embed = (
                discord.Embed(
                    title=f"🔴 {event_info['name']} is live",
                    description=(
                        f"Event website: {event_info['website']}\n"
                        f"CTFtime URL: {CTFTIME_URL}/event/{event_info['id']}"
                    ),
                    color=discord.Colour.red(),
                )
                .set_thumbnail(url=event_info["logo"])
                .add_field(
                    name="Description", value=event_info["description"], inline=False
                )
                .add_field(name="Prizes", value=event_info["prizes"], inline=False)
                .add_field(
                    name="Format",
                    value=f"{event_info['location']} {event_info['format']}",
                    inline=True,
                )
                .add_field(
                    name="Organizers",
                    value=", ".join(event_info["organizers"]),
                    inline=True,
                )
                .add_field(name="Weight", value=event_info["weight"], inline=True)
                .add_field(
                    name="Timeframe",
                    value=f"{event_info['start']}\n{event_info['end']}",
                    inline=False,
                )
            )

            no_running_events = False
            await interaction.followup.send(embed=embed)

        if no_running_events:
            await interaction.followup.send("No ongoing CTFs for the moment.")

    @app_commands.command()
    async def upcoming(
        self, interaction: discord.Interaction, limit: Optional[int] = 3
    ) -> None:
        """Show upcoming events.

        Args:
            interaction: The interaction that triggered this command.
            limit: Number of events to fetch (default: 3, max: 10).
        """
        await interaction.response.defer()

        async with aiohttp.request(
            method="get",
            url=f"{CTFTIME_URL}/api/v1/events/",
            params={"limit": min(limit, 10)},
            headers={"User-Agent": USER_AGENT},
        ) as response:
            if response.status == 200:
                for event in await response.json():
                    event_info = await scrape_event_info(event["id"])
                    if event_info is None:
                        continue

                    embed = (
                        discord.Embed(
                            title=f"🆕 {event_info['name']}",
                            description=(
                                f"Event website: {event_info['website']}\n"
                                f"CTFtime URL: {CTFTIME_URL}/event/{event_info['id']}"
                            ),
                            color=discord.Colour.red(),
                        )
                        .set_thumbnail(url=event_info["logo"])
                        .add_field(
                            name="Description",
                            value=event_info["description"],
                            inline=False,
                        )
                        .add_field(
                            name="Prizes", value=event_info["prizes"], inline=False
                        )
                        .add_field(
                            name="Format",
                            value=f"{event_info['location']} {event_info['format']}",
                            inline=True,
                        )
                        .add_field(
                            name="Organizers",
                            value=", ".join(event_info["organizers"]),
                            inline=True,
                        )
                        .add_field(
                            name="Weight", value=event_info["weight"], inline=True
                        )
                        .add_field(
                            name="Timeframe",
                            value=f"{event_info['start']}\n{event_info['end']}",
                            inline=False,
                        )
                    )

                    no_upcoming_events = False
                    await interaction.followup.send(embed=embed)

                if no_upcoming_events:
                    await interaction.followup.send("No upcoming CTFs.")

    @app_commands.command()
    async def top(self, interaction: discord.Interaction, year: Optional[int]) -> None:
        """Shows CTFtime's leaderboard for a specific year (default: current year).

        Args:
            interaction: The interaction that triggered this command.
            year: Show leaderboard of this year. Defaults to the current year if not
                provided.
        """
        await interaction.response.defer()

        year = year or datetime.today().year
        year = str(year)

        async with aiohttp.request(
            method="get",
            url=f"{CTFTIME_URL}/api/v1/top/{year}/",
            headers={"User-Agent": USER_AGENT},
        ) as response:
            if response.status == 200 and year in (json := await response.json()):
                teams = json[year]
                leaderboard = f"{'[Rank]':<10}{'[Team]':<50}{'[Score]'}\n"

                for rank, team in enumerate(teams, start=1):
                    score = round(team["points"], 4)
                    leaderboard += f"{rank:<10}{team['team_name']:<50}{score}\n"

                await interaction.followup.send(
                    f":triangular_flag_on_post:  **{year} CTFtime Leaderboard**"
                    f"```ini\n{leaderboard.strip()}```"
                )
            else:
                await interaction.followup.send("No results.")
