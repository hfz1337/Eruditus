import logging
import io
import os
import re

from typing import Union

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

from lib.util import setup_logger, truncate, get_local_time, derive_colour
from lib.ctftime import (
    scrape_event_info,
    ctftime_date_to_datetime,
)
from config import CTF_COLLECTION, CTFTIME_URL, DBNAME, GUILD_ID, MONGO, USER_AGENT


class Eruditus(discord.Client):
    def __init__(self) -> None:
        super().__init__(intents=discord.Intents.default())
        self.tree = discord.app_commands.CommandTree(self)

    async def create_ctf(self, name: str, live: bool = True) -> Union[dict, None]:
        """Create a CTF along with its channels and role.

        Args:
            name: CTF name.
            live: True if the CTF is ongoing.

        Returns:
            A dictionary containing information about the created CTF, or None if the
            CTF already exists.
        """
        # Check if the CTF already exists (case insensitive).
        if MONGO[DBNAME][CTF_COLLECTION].find_one(
            {"name": re.compile(f"^{name.strip()}$", re.IGNORECASE)}
        ):
            return None

        # The bot is supposed to be part of a single guild.
        guild = self.get_guild(GUILD_ID)

        # Create the role if it didn't exist.
        role = discord.utils.get(guild.roles, name=name)
        if role is None:
            role = await guild.create_role(
                name=name,
                colour=derive_colour(name),
                mentionable=True,
            )

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            role: discord.PermissionOverwrite(read_messages=True),
        }

        # Create the category channel if it didn't exist.
        category_channel = discord.utils.get(guild.categories, name=name)
        if category_channel is None:
            category_channel = await guild.create_category(
                name=f"{['⏰', '🔴'][live]} {name}",
                overwrites=overwrites,
            )

        await guild.create_text_channel("general", category=category_channel)
        await guild.create_voice_channel("general", category=category_channel)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            role: discord.PermissionOverwrite(read_messages=True, send_messages=False),
        }

        credentials_channel = await guild.create_text_channel(
            name="🔑-credentials", category=category_channel, overwrites=overwrites
        )
        notes_channel = await guild.create_text_channel(
            name="📝-notes", category=category_channel, overwrites=overwrites
        )
        announcement_channel = await guild.create_text_channel(
            name="📣-announcements", category=category_channel, overwrites=overwrites
        )
        solves_channel = await guild.create_text_channel(
            name="🎉-solves", category=category_channel, overwrites=overwrites
        )
        scoreboard_channel = await guild.create_text_channel(
            name="📈-scoreboard", category=category_channel, overwrites=overwrites
        )

        ctf = {
            "name": name,
            "archived": False,
            "credentials": {
                "url": None,
                "username": None,
                "password": None,
            },
            "challenges": [],
            "guild_role": role.id,
            "guild_category": category_channel.id,
            "guild_channels": {
                "announcements": announcement_channel.id,
                "credentials": credentials_channel.id,
                "scoreboard": scoreboard_channel.id,
                "solves": solves_channel.id,
                "notes": notes_channel.id,
            },
        }
        MONGO[DBNAME][CTF_COLLECTION].insert_one(ctf)
        return ctf

    async def setup_hook(self) -> None:
        self.tree.add_command(Help())
        self.tree.add_command(Syscalls())
        self.tree.add_command(Encoding())
        self.tree.add_command(CTFTime())
        self.tree.add_command(Cipher())
        self.tree.add_command(Report())
        self.tree.add_command(Request())
        self.tree.add_command(Search())
        self.tree.add_command(CTF(), guild=discord.Object(GUILD_ID))

        self.create_upcoming_events.start()
        self.ctf_reminder.start()

    async def on_ready(self) -> None:
        for guild in self.guilds:
            logger.info(f"{self.user} connected to {guild}")

        # Sync global and guild specific commands.
        await self.tree.sync()
        await self.tree.sync(guild=discord.Object(id=GUILD_ID))

        await self.change_presence(activity=discord.Game(name="/help"))

    async def on_guild_join(self, guild: discord.Guild) -> None:
        logger.info(f"{self.user} joined {guild}!")

    async def on_guild_remove(self, guild: discord.Guild) -> None:
        logger.info(f"{self.user} left {guild}.")

    async def on_scheduled_event_update(
        self, before: discord.ScheduledEvent, after: discord.ScheduledEvent
    ) -> None:
        # The bot is supposed to be part of a single guild.
        guild = self.get_guild(GUILD_ID)

        # If an event started (status changes from scheduled to active).
        if (
            before.status == discord.EventStatus.scheduled
            and after.status == discord.EventStatus.active
        ):
            # Create the CTF if it wasn't already created.
            ctf = await self.create_ctf(after.name, live=True)
            if ctf is None:
                ctf = MONGO[DBNAME][CTF_COLLECTION].find_one(
                    {"name": re.compile(f"^{after.name.strip()}$", re.IGNORECASE)}
                )

            # Give the CTF role to the interested people if they didn't get it yet.
            role = discord.utils.get(guild.roles, id=ctf["guild_role"])
            async for user in after.users():
                member = await guild.fetch_member(user.id)
                await member.add_roles(role)

            # Substitue the ⏰ in the category channel name with a 🔴 to say that
            # we're live.
            category_channel = discord.utils.get(
                guild.categories, id=ctf["guild_category"]
            )
            await category_channel.edit(name=category_channel.name.replace("⏰", "🔴"))

            # Ping all participants.
            ctf_general_channel = discord.utils.get(
                guild.text_channels,
                category_id=ctf["guild_category"],
                name="general",
            )
            await ctf_general_channel.send(
                f"{role.mention} has started!\nGet to work now ⚔️ 🔪 😠 🔨 ⚒️"
            )

    @tasks.loop(hours=1, reconnect=True)
    async def ctf_reminder(self) -> None:
        """Create a CTF for events starting soon and send a reminder."""
        # Wait until the bot's internal cache is ready.
        await self.wait_until_ready()

        # Timezone aware local time.
        local_time = get_local_time()

        # The bot is supposed to be part of a single guild.
        guild = self.get_guild(GUILD_ID)

        # Find a public channel where we can send our reminders.
        public_channel = None
        for channel in guild.text_channels:
            if channel.permissions_for(guild.default_role).read_messages:
                public_channel = channel
                if "general" in public_channel.name:
                    break

        for scheduled_event in await guild.fetch_scheduled_events():
            if scheduled_event.status != discord.EventStatus.scheduled:
                continue

            remaining_time = scheduled_event.start_time - local_time
            if remaining_time < timedelta(hours=1):
                # If a CTF is starting soon, we create it if it wasn't created yet.
                ctf = await self.create_ctf(scheduled_event.name, live=False)
                if ctf is None:
                    ctf = MONGO[DBNAME][CTF_COLLECTION].find_one(
                        {
                            "name": re.compile(
                                f"^{scheduled_event.name.strip()}$", re.IGNORECASE
                            )
                        }
                    )

                # Add interested people automatically.
                role = discord.utils.get(guild.roles, id=ctf["guild_role"])
                async for user in scheduled_event.users():
                    member = await guild.fetch_member(user.id)
                    await member.add_roles(role)

                # Send a reminder that the CTF is starting soon.
                if public_channel:
                    await public_channel.send(
                        f"🔔 CTF `{ctf['name']}` starting in "
                        f"`{str(remaining_time).split('.')[0]}`.\n"
                        f"@here you can still use `/ctf join` to participate in case "
                        f"you forgot to hit the `Interested` button of the event."
                    )

    @tasks.loop(hours=3, reconnect=True)
    async def create_upcoming_events(self) -> None:
        """Create a Scheduled Event for each upcoming CTF competition."""
        # Wait until the bot's internal cache is ready.
        await self.wait_until_ready()

        # Timezone aware local time.
        local_time = get_local_time()

        # The bot is supposed to be part of a single guild.
        guild = self.get_guild(GUILD_ID)

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
                        raw_image = io.BytesIO(await image.read()).read()

                    event_description = (
                        f"{event_info['description']}\n\n"
                        f"👥 **Organizers**\n{', '.join(event_info['organizers'])}\n\n"
                        f"💰 **Prizes**\n{event_info['prizes']}\n\n"
                        f"⚙️ **Format**\n {event_info['location']} "
                        f"{event_info['format']}\n\n"
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
                            " — "
                            f"{event_info['website']}"
                        ),
                    }

                    # In case the event was already scheduled, we update it, otherwise
                    # we create a new event.
                    if event_info["name"] in scheduled_events:
                        scheduled_event = guild.get_scheduled_event(
                            scheduled_events[event_info["name"]]
                        )
                        scheduled_event = await scheduled_event.edit(**parameters)

                    else:
                        scheduled_event = await guild.create_scheduled_event(
                            **parameters
                        )


if __name__ == "__main__":
    logger = setup_logger(logging.INFO)
    client = Eruditus()
    client.run(os.getenv("DISCORD_TOKEN"))
