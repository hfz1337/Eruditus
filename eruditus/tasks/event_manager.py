from datetime import datetime
import time
import asyncio
import requests

import discord
from discord import RawReactionActionEvent, TextChannel, Role
from discord.ext.commands import Bot
from discord.ext import tasks, commands

from pymongo import MongoClient

from lib.ctftime import scrape_event_info

from config import (
    MONGODB_URI,
    DBNAME_PREFIX,
    CTFTIME_COLLECTION,
    CONFIG_COLLECTION,
    CTF_COLLECTION,
    CTFTIME_URL,
    DATE_FORMAT,
    USER_AGENT,
)

# MongoDB handle
mongo = MongoClient(MONGODB_URI)


class EventManager(commands.Cog):
    """This cog provides background tasks for automatically updating the database with
    new events from CTFtime, announcing approaching events and handling CTF creations
    by enabling team voting.
    """

    def __init__(self, bot: Bot) -> None:
        self._bot = bot
        self._update_events_task = tasks.loop(minutes=30.0, reconnect=True)(
            self.update_events
        )
        self._update_events_task.start()
        self._announce_upcoming_events.start()
        self._voting_verdict.start()

    async def update_events(self) -> None:
        """Update the database with recent events from CTFtime."""
        # Wait until the bot's internal cache is ready
        await self._bot.wait_until_ready()

        # The number of upcoming events to request from the API, we only consider
        # upcoming events
        params = {"limit": 10, "start": int(time.time())}
        headers = {"User-Agent": USER_AGENT}
        response = requests.get(
            url=f"{CTFTIME_URL}/api/v1/events/", params=params, headers=headers
        )

        if response.status_code == 200:
            for event in response.json():
                event_info = scrape_event_info(event["id"])
                if event_info is None:
                    continue

                for guild in self._bot.guilds:
                    # Check if this event was already in the database
                    if mongo[f"{DBNAME_PREFIX}-{guild.id}"][
                        CTFTIME_COLLECTION
                    ].find_one({"id": event_info["id"]}):
                        # In case it was found, we update it
                        mongo[f"{DBNAME_PREFIX}-{guild.id}"][
                            CTFTIME_COLLECTION
                        ].update_one({"id": event_info["id"]}, {"$set": event_info})
                    else:
                        # If this event was new, we add the `announced` and `created`
                        # booleans, as well as a field to save the announcement message
                        # id when the event gets announced
                        event_info["announced"] = False
                        event_info["created"] = False
                        event_info["announcement"] = None
                        mongo[f"{DBNAME_PREFIX}-{guild.id}"][
                            CTFTIME_COLLECTION
                        ].insert_one(event_info)

        # Prune CTFs that ended
        for guild in self._bot.guilds:
            mongo[f"{DBNAME_PREFIX}-{guild.id}"][CTFTIME_COLLECTION].delete_many(
                {"end": {"$lt": int(time.time())}}
            )

    @tasks.loop(minutes=10.0, reconnect=True)
    async def _announce_upcoming_events(self) -> None:
        """Announce upcoming CTF competitions."""
        # Wait until the bot's internal cache is ready
        await self._bot.wait_until_ready()

        for guild in self._bot.guilds:
            # Get guild config from the database
            config = mongo[f"{DBNAME_PREFIX}-{guild.id}"][CONFIG_COLLECTION].find_one()
            announcement_channel = await self._bot.fetch_channel(
                config["announcement_channel"]
            )

            # Get non-announced events starting in less than `voting_starts_countdown`
            # seconds
            now = int(time.time())
            query_filter = {
                "start": {"$lt": now + config["voting_starts_countdown"], "$gt": now},
                "announced": False,
            }

            for event in mongo[f"{DBNAME_PREFIX}-{guild.id}"][CTFTIME_COLLECTION].find(
                query_filter
            ):
                # Convert timestamps to dates
                start_date = datetime.strftime(
                    datetime.fromtimestamp(event["start"]), DATE_FORMAT
                )
                end_date = datetime.strftime(
                    datetime.fromtimestamp(event["end"]), DATE_FORMAT
                )

                embed = (
                    discord.Embed(
                        title=f"➡️ {event['name']}",
                        description=(
                            f"Event website: {event['website']}\n"
                            f"CTFtime URL: {CTFTIME_URL}/event/{event['id']}"
                        ),
                        color=discord.Colour.red(),
                    )
                    .set_thumbnail(url=event["logo"])
                    .add_field(
                        name="Description", value=event["description"], inline=False
                    )
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
                        value=f"{start_date}\n{end_date}",
                        inline=False,
                    )
                )

                message = await announcement_channel.send(embed=embed)

                # Add voting reactions to the message
                await message.add_reaction("👍")
                await message.add_reaction("👎")

                event["announced"] = True
                event["announcement"] = message.id

                event_object_id = event["_id"]
                del event["_id"]
                mongo[f"{DBNAME_PREFIX}-{guild.id}"][CTFTIME_COLLECTION].update_one(
                    {"_id": event_object_id}, {"$set": event}
                )

    @tasks.loop(minutes=10.0, reconnect=True)
    async def _voting_verdict(self) -> None:
        """Decide whether or not to create an approaching CTF according to the vote
        results represented by the number of reactions.
        """
        # Wait until the bot's internal cache is ready
        await self._bot.wait_until_ready()

        for guild in self._bot.guilds:
            # Get guild config from the database
            config = mongo[f"{DBNAME_PREFIX}-{guild.id}"][CONFIG_COLLECTION].find_one()
            if config is None:
                return
            announcement_channel = await self._bot.fetch_channel(
                config["announcement_channel"]
            )

            # Get announced events starting in less than `voting_verdict_countdown`
            # seconds
            now = int(time.time())
            query_filter = {
                "start": {
                    "$lt": now + config["voting_verdict_countdown"],
                    "$gt": now,
                },
                "announced": True,
                "created": False,
            }
            for event in mongo[f"{DBNAME_PREFIX}-{guild.id}"][CTFTIME_COLLECTION].find(
                query_filter
            ):
                # Get the announcement message
                message = await announcement_channel.fetch_message(
                    event["announcement"]
                )
                vote_yes = discord.utils.get(message.reactions, emoji="👍")

                # If we got enough votes, we create the CTF
                if vote_yes.count > config["minimum_player_count"]:
                    # Get context from our announcement message
                    ctx = await self._bot.get_context(message)
                    # Invoke the CTF cog to create the event
                    await self._bot.get_cog("CTF").createctf.invoke(
                        ctx, name=event["name"]
                    )

                    # Send a message with the @everyone mention in the announcements
                    # channel with instructions on how to join the CTF
                    await announcement_channel.send(
                        f"{announcement_channel.guild.default_role}\n"
                        "A new CTF has been created, you can joing using "
                        f"`/ctf join \"{event['name']}\"`"
                    )
                    # Update the `created` field
                    mongo[f"{DBNAME_PREFIX}-{guild.id}"][CTFTIME_COLLECTION].update_one(
                        {"_id": event["_id"]}, {"$set": {"created": True}}
                    )

                    ctf = mongo[f"{DBNAME_PREFIX}-{guild.id}"][CTF_COLLECTION].find_one(
                        {"name": event["name"]}
                    )
                    # Start a countdown reminder
                    general_channel = discord.utils.get(
                        ctx.guild.text_channels,
                        category_id=ctf["guild_category"],
                        name="general",
                    )
                    role = discord.utils.get(ctx.guild.roles, id=ctf["guild_role"])
                    timeleft = int(event["start"] - time.time())

                    # Instead of using the @tasks.loop wrapper function around our
                    # `ctf_started_reminder` function, we use this trick to have a
                    # different function object everytime, thus having a different
                    # background task and allowing the function to be run multiple
                    # times at the same time. This is useful if there are more than
                    # 1 CTF starting soon
                    tasks.loop(count=1)(self._ctf_started_reminder).start(
                        timeleft, general_channel, role
                    )

    async def _ctf_started_reminder(
        self, countdown: int, channel: TextChannel, role: Role
    ):
        """Send a reminder message to the `general` CTF channel when the CTF starts.

        Args:
            channel: The guild's text channel where the reminder is sent.
            role: The guild's role to mention on the message.
        """
        await asyncio.sleep(countdown)
        await channel.category.edit(name=channel.category.name.replace("⏰", "🔴"))
        await channel.send(
            f"**{role.mention} CTF has started, on to your computers! 💻**"
        )

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: RawReactionActionEvent) -> None:
        """Prevent a member from adding both votes to the announcement message
        simultaneously.

        Args:
            payload: Payload for the `on_raw_reaction_add` event.
        """
        # If the reaction was added by us, do nothing
        if payload.member.id == self._bot.user.id:
            return

        # Get the message that got a reaction added
        channel = await self._bot.fetch_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)

        # If the concerned message doesn't belong to us, do nothing
        if message.author.id != self._bot.user.id:
            return

        for reaction in message.reactions:
            # Remove all reactions from that user except the one they just added
            if str(reaction) != str(payload.emoji):
                await message.remove_reaction(reaction.emoji, payload.member)


def setup(bot: Bot) -> None:
    """Add the extension to the bot."""
    bot.add_cog(EventManager(bot))
