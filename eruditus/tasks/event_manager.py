from discord import RawReactionActionEvent, TextChannel, Role
from discord.ext.commands import Bot
from discord.ext import tasks, commands
from pymongo import MongoClient
from datetime import datetime
from lib.ctftime import scrape_event_info
import requests
import asyncio
import discord
import time
from config import (
    MONGODB_URI,
    DBNAME,
    CTFTIME_EVENTS_COLLECTION,
    CHANNELS_COLLECTION,
    CTFS_COLLECTION,
    CTFTIME_URL,
    DATE_FORMAT,
    EVENT_ANNOUNCEMENT_CHANNEL,
    MINIMUM_PLAYER_COUNT,
    USER_AGENT,
    VOTING_STARTS_COUNTDOWN,
    VOTING_VERDICT_COUNTDOWN,
)

# MongoDB handle
mongo = MongoClient(MONGODB_URI)[DBNAME]


class EventManager(commands.Cog):
    def __init__(self, bot: Bot) -> None:
        self._bot = bot
        self._announcement_channel = None
        self._update_events.start()
        self._announce_upcoming_events.start()
        self._voting_verdict.start()

    async def _get_announcement_channel(self) -> TextChannel:
        if self._announcement_channel is not None:
            return self._announcement_channel

        # If the EVENT_ANNOUNCEMENT_CHANNEL is provided and it's numeric, check if
        # it corresponds to a channel in the guild.
        if EVENT_ANNOUNCEMENT_CHANNEL and EVENT_ANNOUNCEMENT_CHANNEL.isdigit():
            announcement_channel = discord.utils.get(
                self._bot.guilds[0].text_channels, id=int(EVENT_ANNOUNCEMENT_CHANNEL)
            )
        else:
            announcement_channel = None

        # If the provided channel didn't exist, we try to fetch it from the database
        if announcement_channel is None:
            announcement_channel = mongo[CHANNELS_COLLECTION].find_one(
                {"name": "announcement"}
            )
            # If the channel was found in the database, we fetch it
            if announcement_channel:
                announcement_channel = discord.utils.get(
                    self._bot.guilds[0].text_channels, id=announcement_channel["id"]
                )

        return announcement_channel

    @tasks.loop(minutes=30.0, reconnect=True)
    async def _update_events(self) -> None:
        # Wait until the bot's internal cache is ready
        await self._bot.wait_until_ready()

        # The number of upcoming events to request from the API
        # We only consider upcoming events, that's why we set the start parameter to
        # the current time
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
                if list(
                    mongo[CTFTIME_EVENTS_COLLECTION].find({"id": event_info["id"]})
                ):
                    # In case it was found, we update all its fields, except the
                    # `announced` boolean.
                    mongo[CTFTIME_EVENTS_COLLECTION].update(
                        {"id": event_info["id"]}, {"$set": event_info}
                    )
                else:
                    # If this event was new, we add the `announced` and `created`
                    # booleans, as well as a field to save the announcement message
                    # id when the event gets announced
                    event_info["announced"] = False
                    event_info["created"] = False
                    event_info["announcement"] = None
                    mongo[CTFTIME_EVENTS_COLLECTION].insert_one(event_info)

        # Prune CTFs that ended
        mongo[CTFTIME_EVENTS_COLLECTION].delete_many({"end": {"$lt": int(time.time())}})

    @tasks.loop(minutes=30.0, reconnect=True)
    async def _announce_upcoming_events(self) -> None:
        # Wait until the bot's internal cache is ready
        await self._bot.wait_until_ready()

        announcement_channel = await self._get_announcement_channel()
        # If the channel wasn't we create it and save it to the database for future use
        if not announcement_channel:
            overwrites = {
                self._bot.guilds[0].default_role: discord.PermissionOverwrite(
                    send_messages=False, add_reactions=False
                )
            }
            announcement_channel = await self._bot.guilds[0].create_text_channel(
                name="📢 Event Announcements",
                overwrites=overwrites,
            )
            mongo[CHANNELS_COLLECTION].update(
                {"name": "announcement"},
                {"$set": {"name": "announcement", "id": announcement_channel.id}},
                upsert=True,
            )
            self._announcement_channel = announcement_channel

        # Get non-announced events starting in less than `VOTING_STARTS_COUNTDOWN`
        # seconds
        now = int(time.time())
        query_filter = {
            "start": {"$lt": now + VOTING_STARTS_COUNTDOWN, "$gt": now},
            "announced": False,
        }

        for event in mongo[CTFTIME_EVENTS_COLLECTION].find(query_filter):
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

            mongo[CTFTIME_EVENTS_COLLECTION].update(
                {"_id": event["_id"]}, {"$set": event}
            )

    @tasks.loop(minutes=15.0, reconnect=True)
    async def _voting_verdict(self) -> None:
        # Wait until the bot's internal cache is ready
        await self._bot.wait_until_ready()

        # Get the announcements channel
        announcement_channel = await self._get_announcement_channel()
        if not announcement_channel:
            return

        # Get announced events starting in less than `VOTING_VERDICT_COUNTDOWN` seconds
        now = int(time.time())
        query_filter = {
            "start": {"$lt": now + VOTING_VERDICT_COUNTDOWN, "$gt": now},
            "announced": True,
            "created": False,
        }
        for event in mongo[CTFTIME_EVENTS_COLLECTION].find(query_filter):
            # Get the announcement message
            message = await announcement_channel.fetch_message(event["announcement"])
            vote_yes = discord.utils.get(message.reactions, emoji="👍")

            # If we got enough votes, we create the CTF
            if vote_yes.count > MINIMUM_PLAYER_COUNT:
                # Create the CTF by invoking "!ctf createctf"
                ctx = await self._bot.get_context(message)
                await ctx.invoke(
                    self._bot.get_command("ctf createctf"), ctf_name=event["name"]
                )

                # Send a message with the @everyone mention in the announcements channel
                # with instructions on how to join the CTF
                await announcement_channel.send(
                    f"{announcement_channel.guild.default_role}\n"
                    "A new CTF has been created, you can joing using "
                    f"`{self._bot.command_prefix}ctf join \"{event['name']}\"`"
                )
                # Update the `created` field
                event["created"] = True
                mongo[CTFTIME_EVENTS_COLLECTION].update(
                    {"_id": event["_id"]}, {"$set": event}
                )

                ctf_info = mongo[CTFS_COLLECTION].find_one({"name": event["name"]})
                # Start a countdown reminder
                general_channel = discord.utils.get(
                    ctx.guild.text_channels,
                    category_id=ctf_info["category_channel_id"],
                    name="general",
                )
                role = discord.utils.get(ctx.guild.roles, id=ctf_info["role_id"])
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
        await asyncio.sleep(countdown)
        await channel.category.edit(name=channel.category.name.replace("⏰", "🔴"))
        await channel.send(
            f"**{role.mention} CTF has started, on to your computers! 💻**"
        )

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: RawReactionActionEvent) -> None:
        """Prevents a member from adding both votes to the announcement message
        simultaneously.
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
    bot.add_cog(EventManager(bot))
