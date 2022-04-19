import logging
import os

import discord
from discord.ext import tasks

from datetime import timedelta

import aiohttp

from slash_commands.help import Help
from slash_commands.syscalls import Syscalls
from slash_commands.encoding import Encoding
from slash_commands.ctftime import CTFTime
from slash_commands.cipher import Cipher
from slash_commands.report import Report
from slash_commands.request import Request
from slash_commands.search import Search
from slash_commands.ctf import CTF

from lib.util import setup_logger, truncate, get_local_time
from lib.ctftime import (
    scrape_event_info,
    ctftime_date_to_datetime,
)
from config import CTFTIME_URL, GUILD_ID, USER_AGENT

# Setup logging
logger = setup_logger(logging.INFO)


class Eruditus(discord.Client):
    def __init__(self) -> None:
        super().__init__(intents=discord.Intents.default())
        self.tree = discord.app_commands.CommandTree(self)

    async def setup_hook(self) -> None:
        self.tree.add_command(Help(), guild=discord.Object(GUILD_ID))
        self.tree.add_command(Syscalls(), guild=discord.Object(GUILD_ID))
        self.tree.add_command(Encoding(), guild=discord.Object(GUILD_ID))
        self.tree.add_command(CTFTime(), guild=discord.Object(GUILD_ID))
        self.tree.add_command(Cipher(), guild=discord.Object(GUILD_ID))
        self.tree.add_command(Report(), guild=discord.Object(GUILD_ID))
        self.tree.add_command(Request(), guild=discord.Object(GUILD_ID))
        self.tree.add_command(Search(), guild=discord.Object(GUILD_ID))
        self.tree.add_command(CTF(), guild=discord.Object(GUILD_ID))

        self.create_upcoming_events.start()

    async def on_ready(self) -> None:
        for guild in self.guilds:
            # Setup guild database if it wasn't already
            # if not mongo[f"{DBNAME_PREFIX}-{guild.id}"][CONFIG_COLLECTION].find_one():
            #     await setup_database(mongo, guild)
            logger.info(f"{self.user} connected to {guild}")

        # Sync global and guild specific commands.
        await self.tree.sync()
        await self.tree.sync(guild=discord.Object(id=GUILD_ID))

        await self.change_presence(activity=discord.Game(name="/help"))

    async def on_guild_join(self, guild: discord.Guild) -> None:
        """Set up a database for the newly joined guild."""
        # await setup_database(mongo, guild)
        logger.info(f"{self.user} joined {guild}!")

    async def on_guild_remove(self, guild: discord.Guild) -> None:
        """Delete the database for the guild we just left."""
        # mongo.drop_database(f"{DBNAME_PREFIX}-{guild.id}")
        logger.info(f"{self.user} left {guild}.")

    async def on_scheduled_event_update(
        self, before: discord.ScheduledEvent, after: discord.ScheduledEvent
    ) -> None:
        # If an event started, create an associated CTF category and add interested
        # people to it.
        if (
            before.status == discord.EventStatus.scheduled
            and after.status == discord.EventStatus.active
        ):
            async for user in after.users():
                print(user)

    @tasks.loop(hours=1, reconnect=True)
    async def create_upcoming_events(self) -> None:
        """Create a Scheduled Event for each upcoming CTF competition."""
        # Wait until the bot's internal cache is ready
        await self.wait_until_ready()

        # Timezone aware local time.
        local_time = get_local_time()

        # The bot is supposed to be part of a single guild.
        guild = self.guilds[0]

        # Get scheduled events for this guild.
        scheduled_events = {
            scheduled_event.name: scheduled_event.id
            for scheduled_event in await guild.fetch_scheduled_events()
        }

        async with aiohttp.request(
            method="get",
            url=f"{CTFTIME_URL}/api/v1/events/",
            params={"limit": 10},
            headers={"User-Agent": USER_AGENT},
        ) as response:
            if response.status == 200:
                for event in await response.json():
                    event_info = await scrape_event_info(event["id"])
                    if event_info is None:
                        continue

                    event_start = ctftime_date_to_datetime(event_info["start"])
                    event_end = ctftime_date_to_datetime(event_info["end"])

                    # If the event starts in more than a week, then it's too soon to
                    # schedule it, we ignore it for now.
                    if event_start > local_time + timedelta(weeks=1):
                        continue

                    async with aiohttp.request(
                        method="get",
                        url=event_info["logo"],
                        headers={"User-Agent": USER_AGENT},
                    ) as image:
                        raw_image = await image.read()

                    event_description = (
                        f"{event_info['description']}\n\n"
                        f"👥 **Organizers**\n{', '.join(event_info['organizers'])}\n\n"
                        f"💰 **Prizes**\n{event_info['prizes']}\n\n"
                        f"⚙️ **Format**\n {event_info['location']} {event_info['format']}\n\n"
                        f"🎯 **Weight**\n{event_info['weight']}"
                    )
                    parameters = {
                        "name": event_info["name"],
                        "description": truncate(text=event_description, maxlen=1000),
                        "start_time": event_start,
                        "end_time": event_end,
                        "entity_type": discord.EntityType.external,
                        "image": raw_image,
                        "location": (
                            f"{CTFTIME_URL}/event/{event_info['id']}"
                            " & "
                            f"{event_info['website']}"
                        ),
                    }

                    # In case the event was already scheduled, we update it, otherwise
                    # we create a new event.
                    if event_info["name"] in scheduled_events:
                        scheduled_event = guild.get_scheduled_event(
                            scheduled_events[event_info["name"]]
                        )
                        if scheduled_event.status == discord.EventStatus.scheduled:
                            scheduled_event = await scheduled_event.edit(**parameters)

                    else:
                        scheduled_event = await guild.create_scheduled_event(
                            **parameters
                        )


client = Eruditus()
client.run(os.getenv("DISCORD_TOKEN"))
