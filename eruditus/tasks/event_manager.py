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
    DBNAME,
    CTFTIME_COLLECTION,
    CONFIG_COLLECTION,
    CTF_COLLECTION,
    CTFTIME_URL,
    DATE_FORMAT,
    USER_AGENT,
)

# MongoDB handle
mongo = MongoClient(MONGODB_URI)[DBNAME]


class EventManager(commands.Cog):
    """This cog provides background tasks for automatically updating the database with
    new events from CTFtime, announcing approaching events and handling CTF creations
    by enabling team voting.
    """

    def __init__(self, bot: Bot) -> None:
        self._bot = bot
        self._config = mongo[CONFIG_COLLECTION].find_one()
        self._update_events.start()
        self._announce_upcoming_events.start()
        self._voting_verdict.start()

    async def _get_announcement_channel(self) -> TextChannel:
        """Attempts to retrieve the announcement channel if it already exists.

        Returns:
            The announcements channel.

        """
        if self._config["announcement_channel"]:
            return await self._bot.fetch_channel(self._config["announcement_channel"])

        return None

    @tasks.loop(minutes=30.0, reconnect=True)
    async def _update_events(self) -> None:
        """Updates the database with recent events from CTFtime."""
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

                # Check if this event was already in the database
                if mongo[CTFTIME_COLLECTION].find_one({"id": event_info["id"]}):
                    # In case it was found, we update all its fields, except the
                    # `announced` boolean.
                    mongo[CTFTIME_COLLECTION].update_one(
                        {"id": event_info["id"]}, {"$set": event_info}
                    )
                else:
                    # If this event was new, we add the `announced` and `created`
                    # booleans, as well as a field to save the announcement message
                    # id when the event gets announced
                    event_info["announced"] = False
                    event_info["created"] = False
                    event_info["announcement"] = None
                    mongo[CTFTIME_COLLECTION].insert_one(event_info)

        # Prune CTFs that ended
        mongo[CTFTIME_COLLECTION].delete_many({"end": {"$lt": int(time.time())}})

    @tasks.loop(minutes=30.0, reconnect=True)
    async def _announce_upcoming_events(self) -> None:
        """Announces upcoming CTF competitions."""
        # Wait until the bot's internal cache is ready
        await self._bot.wait_until_ready()

        announcement_channel = await self._get_announcement_channel()
        # If the channel didn't exist, we create it and save it to the database for
        # future use
        if announcement_channel is None:
            overwrites = {
                self._bot.guilds[0].default_role: discord.PermissionOverwrite(
                    send_messages=False, add_reactions=False
                )
            }
            announcement_channel = await self._bot.guilds[0].create_text_channel(
                name="📢 Event Announcements",
                overwrites=overwrites,
            )
            self._config["announcement_channel"] = announcement_channel.id
            mongo[CONFIG_COLLECTION].update_one(
                {"_id": self._config["_id"]},
                {
                    "$set": {
                        "announcement_channel": self._config["announcement_channel"]
                    }
                },
            )

        # Get non-announced events starting in less than `voting_starts_countdown`
        # seconds
        now = int(time.time())
        query_filter = {
            "start": {"$lt": now + self._config["voting_starts_countdown"], "$gt": now},
            "announced": False,
        }

        for event in mongo[CTFTIME_COLLECTION].find(query_filter):
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

            mongo[CTFTIME_COLLECTION].update_one({"_id": event["_id"]}, {"$set": event})

    @tasks.loop(minutes=15.0, reconnect=True)
    async def _voting_verdict(self) -> None:
        """Decides whether or not to create an approaching CTF according to the vote
        results represented by the number of reactions.
        """
        # Wait until the bot's internal cache is ready
        await self._bot.wait_until_ready()

        # Get the announcements channel
        announcement_channel = await self._get_announcement_channel()
        if announcement_channel is None:
            return

        # Get announced events starting in less than `voting_verdict_countdown` seconds
        now = int(time.time())
        query_filter = {
            "start": {
                "$lt": now + self._config["voting_verdict_countdown"],
                "$gt": now,
            },
            "announced": True,
            "created": False,
        }
        for event in mongo[CTFTIME_COLLECTION].find(query_filter):
            # Get the announcement message
            message = await announcement_channel.fetch_message(event["announcement"])
            vote_yes = discord.utils.get(message.reactions, emoji="👍")

            # If we got enough votes, we create the CTF
            if vote_yes.count > self._config["minimum_player_count"]:
                # Get context from our announcement message
                ctx = await self._bot.get_context(message)
                # Invoke the CTF cog to create the event
                await self._bot.get_cog("CTF").createctf.invoke(ctx, name=event["name"])

                # Send a message with the @everyone mention in the announcements channel
                # with instructions on how to join the CTF
                await announcement_channel.send(
                    f"{announcement_channel.guild.default_role}\n"
                    "A new CTF has been created, you can joing using "
                    f"`/ctf join \"{event['name']}\"`"
                )
                # Update the `created` field
                mongo[CTFTIME_COLLECTION].update_one(
                    {"_id": event["_id"]}, {"$set": {"created": True}}
                )

                ctf = mongo[CTF_COLLECTION].find_one({"name": event["name"]})
                # Start a countdown reminder
                general_channel = discord.utils.get(
                    ctx.guild.text_channels,
                    category_id=ctf["guild_category"],
                    name="general",
                )
                role = discord.utils.get(ctx.guild.roles, id=ctf["guild_role"])
                timeleft = int(event["start"] - time.time())

                # Instead of using the @tasks.loop wrapper function around our
                # `ctf_started_reminder` function, we use this trick to have a different
                # function object everytime, thus having a different background task and
                # allowing the function to be run multiple times at the same time.
                # This is useful if there are more than 1 CTF starting soon
                tasks.loop(count=1)(self._ctf_started_reminder).start(
                    timeleft, general_channel, role
                )

    async def _ctf_started_reminder(
        self, countdown: int, channel: TextChannel, role: Role
    ):
        """Sends a reminder message to the `general` CTF channel when the CTF starts.

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
        """Prevents a member from adding both votes to the announcement message
        simultaneously.

        Args:
            payload: Payload for the `on_raw_reaction_add` event.

        """
        # If the reaction was added by us, do nothing
        if payload.member.id == self._bot.user.id:
            return

        announcement_channel = await self._get_announcement_channel()
        if payload.channel_id == announcement_channel.id:
            message = await announcement_channel.fetch_message(payload.message_id)
            for reaction in message.reactions:
                # Remove all reactions from that user except the one they just added
                if str(reaction) != str(payload.emoji):
                    await message.remove_reaction(reaction.emoji, payload.member)


def setup(bot: Bot) -> None:
    """Adds the extension to the bot."""
    bot.add_cog(EventManager(bot))
