from datetime import datetime
from typing import Optional

import aiohttp
import config
import discord
from config import CTFTIME_URL, GUILD_ID, USER_AGENT
from constants import EmbedColours, Emojis
from discord import app_commands
from dotenv import set_key
from integrations.ctftime import (
    create_discord_events,
    scrape_current_events,
    scrape_event_info,
)
from utils.responses import send_response


def _create_event_embed(event_info: dict, title_prefix: str) -> discord.Embed:
    """Create a Discord embed for a CTFtime event.

    Args:
        event_info: The event information dictionary.
        title_prefix: The prefix for the embed title
            (e.g., "🔴" for live, "🆕" for upcoming).

    Returns:
        A Discord embed with the event information.
    """
    return (
        discord.Embed(
            title=f"{title_prefix} {event_info['name']}",
            description=(
                f"Event website: {event_info['website']}\n"
                f"CTFtime URL: {CTFTIME_URL}/event/{event_info['id']}"
            ),
            color=EmbedColours.FIRST_BLOOD,
        )
        .set_thumbnail(url=event_info["logo"])
        .add_field(name="Description", value=event_info["description"], inline=False)
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


class CTFTime(app_commands.Group):
    """Show information about ongoing/upcoming events, as well as rankings
    from CTFtime.
    """

    def __init__(self) -> None:
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
            if event_info is None:
                # FIXME Attempt to pull the current events from the REST API.
                continue

            embed = _create_event_embed(event_info, Emojis.LIVE)
            embed.title = f"{Emojis.LIVE} {event_info['name']} is live"

            no_running_events = False
            await interaction.followup.send(embed=embed)

        if no_running_events:
            await send_response(interaction, "No ongoing CTFs for the moment.")

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
            params={"limit": str(min(limit, 10))},
            headers={"User-Agent": USER_AGENT()},
        ) as response:
            if response.status != 200:
                return

            no_upcoming_events = True
            for event in await response.json():
                event_info = await scrape_event_info(event["id"])
                if event_info is None:
                    # Cloudflare protection, unable to scrape the event page.
                    event_info = event
                    event_info["name"] = event_info["title"]
                    event_info["website"] = event_info["url"]
                    event_info["prizes"] = "Visit the event page for more information."
                    event_info["organizers"] = [
                        organizer["name"] for organizer in event_info["organizers"]
                    ]
                    event_info["end"] = event_info["finish"]

                embed = _create_event_embed(event_info, "🆕")

                no_upcoming_events = False
                await interaction.followup.send(embed=embed)

            if no_upcoming_events:
                await send_response(interaction, "No upcoming CTFs.")

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
            headers={"User-Agent": USER_AGENT()},
        ) as response:
            if response.status == 200 and year in (json := await response.json()):
                teams = json[year]
                leaderboard = f"{'[Rank]':<10}{'[Team]':<50}{'[Score]'}\n"

                for rank, team in enumerate(teams, start=1):
                    score = round(team["points"], 4)
                    leaderboard += f"{rank:<10}{team['team_name']:<50}{score}\n"

                await send_response(
                    interaction,
                    f":triangular_flag_on_post:  **{year} CTFtime Leaderboard**"
                    f"```ini\n{leaderboard.strip()}```",
                    ephemeral=False,
                )
            else:
                await send_response(interaction, "No results.")

    @app_commands.checks.has_permissions(manage_events=True)
    @app_commands.command()
    async def pull(self, interaction: discord.Interaction) -> None:
        """Pull events starting in less than a week."""
        await interaction.response.defer()
        await create_discord_events(guild=interaction.client.get_guild(GUILD_ID))
        await send_response(interaction, f"{Emojis.SUCCESS} Done pulling events")

    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.command()
    async def setchannel(
        self, interaction: discord.Interaction, channel_id: Optional[str]
    ) -> None:
        """Set the text channel where CTF reminders will be sent.

        Args:
            interaction: The interaction that triggered this command.
            channel_id: The channel ID.
        """
        # The bot is supposed to be part of a single guild.
        guild = interaction.client.get_guild(GUILD_ID)

        if channel_id is None:
            reminder_channel = guild.get_channel(config.REMINDER_CHANNEL)
            await send_response(
                interaction,
                "Current reminder channel: {}".format(
                    f"<#{reminder_channel.id}>"
                    if reminder_channel is not None
                    else "Not found."
                ),
            )
            return

        # Since integers greater than 2^53 - 1 aren't accepted in JSON, we can't set
        # channel_id to be of type `int`, and let Discord validate the input for us.
        # Instead, we use `str` and do the validation ourselves.
        # https://github.com/discord/discord-api-docs/issues/2448#issuecomment-753820715
        if not channel_id.isdigit():
            await send_response(interaction, "Channel ID must be numeric.")
            return

        channel_id = int(channel_id)

        # Check if the channel exists.
        reminder_channel = guild.get_channel(channel_id)
        if reminder_channel is None:
            await send_response(interaction, "No such channel.")
            return

        config.REMINDER_CHANNEL = reminder_channel.id
        set_key(".env", "REMINDER_CHANNEL", str(config.REMINDER_CHANNEL))
        await send_response(interaction, f"{Emojis.SUCCESS} Reminder channel updated.")
