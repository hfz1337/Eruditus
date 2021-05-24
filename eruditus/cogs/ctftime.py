#
# Eruditus - CTFtime cog
#
# ======================================================================================
# Tracks event information from CTFime.org:
# - Show upcoming events
# - Show ongoing events
# - Show a specific year's leaderboard
# ======================================================================================

from discord import RawReactionActionEvent, TextChannel, Role
from discord.ext.commands import Context, Bot
from discord.ext import tasks, commands
from pymongo import MongoClient
from bs4 import BeautifulSoup
from datetime import datetime
from typing import Generator
from help import help_info
import requests
import asyncio
import discord
import time
import os

# Load environment variables
MONGODB_URI = os.getenv("MONGODB_URI")
CTFTIME_EVENTS_COLLECTION = os.getenv("CTFTIME_EVENTS_COLLECTION")
CHANNELS_COLLECTION = os.getenv("CHANNELS_COLLECTION")
CTFS_COLLECTION = os.getenv("CTFS_COLLECTION")
EVENT_ANNOUNCEMENT_CHANNEL = os.getenv("EVENT_ANNOUNCEMENT_CHANNEL")
DBNAME = os.getenv("DBNAME")
MINIMUM_PLAYER_COUNT = int(os.getenv("MINIMUM_PLAYER_COUNT"))
VOTING_VERDICT_COUNTDOWN = int(os.getenv("VOTING_VERDICT_COUNTDOWN"))
VOTING_STARTS_COUNTDOWN = int(os.getenv("VOTING_STARTS_COUNTDOWN"))

# CTFtime's nginx server is configured to block requests with specific
# user agents, like those containing "python-requests".
USER_AGENT = "Eruditus"

# Date format used by CTFtime
DATE_FORMAT = "%a, %d %B %Y, %H:%M UTC"

# CTFtime website
CTFTIME_URL = "https://ctftime.org"

# MongoDB handle
mongo = MongoClient(MONGODB_URI)[DBNAME]


def scrape_event_info(event_id: int) -> dict:
    response = requests.get(
        url=f"{CTFTIME_URL}/event/{event_id}", headers={"User-Agent": USER_AGENT}
    )
    if response.status_code != 200:
        return None

    parser = BeautifulSoup(response.content, "html.parser")

    event_name = parser.find("h2").text.strip()
    event_location = parser.select_one("p b").text.strip()
    event_format = parser.select_one("p:nth-child(5)").text.split(": ")[1].strip()
    event_website = parser.select_one("p:nth-child(6) a").text
    event_logo = parser.select_one(".span2 img")["src"]
    event_weight = parser.select_one("p:nth-child(8)").text.split(": ")[1].strip()
    event_organizers = [
        organizer.text.strip() for organizer in parser.select(".span10 li a")
    ]
    event_start, event_end = (
        parser.select_one(".span10 p:nth-child(1)")
        .text.replace(" UTC", "")
        .strip()
        .split(" — ")
    )
    event_start, event_end = f"{event_start} UTC", f"{event_end} UTC"

    # Get rid of anchor elements to parse the description and prizes correctly
    for anchor in parser.findAll("a"):
        anchor.replaceWithChildren()
    # Replace br tags with a linebreak
    for br in parser.findAll("br"):
        br.replaceWith("\n")

    event_description = "\n".join(
        p.getText() for p in parser.select("#id_description p")
    )
    event_prizes = "\n".join(p.getText() for p in parser.select("h3+ .well p"))
    event_prizes = event_prizes or "No prizes."

    return {
        "id": event_id,
        "name": event_name,
        "description": event_description,
        "prizes": event_prizes,
        "location": event_location,
        "format": event_format,
        "website": event_website,
        "logo": f"{CTFTIME_URL}{event_logo}",
        "weight": event_weight,
        "organizers": event_organizers,
        "start": event_start,
        "end": event_end,
    }


def scrape_current_events() -> Generator[int, None, None]:
    response = requests.get(url=CTFTIME_URL, headers={"User-Agent": "Eruditus"})
    parser = BeautifulSoup(response.content, "html.parser")

    # Get ongoing events from the home page
    event_ids = [
        int(event["href"].split("/")[-1]) for event in parser.select("td span+ a")
    ]

    for event_id in event_ids:
        yield scrape_event_info(event_id)


class CTFTime(commands.Cog):
    def __init__(self, bot: Bot) -> None:
        self.bot = bot
        self.announcement_channel = None
        self.update_events.start()
        self.announce_upcoming_events.start()
        self.voting_verdict.start()

    async def get_announcement_channel(self) -> TextChannel:
        if self.announcement_channel is not None:
            return self.announcement_channel

        # If the EVENT_ANNOUNCEMENT_CHANNEL is provided and it's numeric, check if
        # it corresponds to a channel in the guild.
        if EVENT_ANNOUNCEMENT_CHANNEL and EVENT_ANNOUNCEMENT_CHANNEL.isdigit():
            announcement_channel = discord.utils.get(
                self.bot.guilds[0].text_channels, id=int(EVENT_ANNOUNCEMENT_CHANNEL)
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
                    self.bot.guilds[0].text_channels, id=announcement_channel["id"]
                )

        return announcement_channel

    @tasks.loop(minutes=30.0, reconnect=True)
    async def update_events(self) -> None:
        # Wait until the bot's internal cache is ready
        await self.bot.wait_until_ready()

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

                # Convert dates to timestamps
                event_info["start"] = int(
                    datetime.strptime(event_info["start"], DATE_FORMAT).timestamp()
                )
                event_info["end"] = int(
                    datetime.strptime(event_info["end"], DATE_FORMAT).timestamp()
                )

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
    async def announce_upcoming_events(self) -> None:
        # Wait until the bot's internal cache is ready
        await self.bot.wait_until_ready()

        announcement_channel = await self.get_announcement_channel()
        # If the channel wasn't we create it and save it to the database for future use
        if not announcement_channel:
            overwrites = {
                self.bot.guilds[0].default_role: discord.PermissionOverwrite(
                    send_messages=False, add_reactions=False
                )
            }
            announcement_channel = await self.bot.guilds[0].create_text_channel(
                name="📢 Event Announcements",
                overwrites=overwrites,
            )
            mongo[CHANNELS_COLLECTION].update(
                {"name": "announcement"},
                {"$set": {"name": "announcement", "id": announcement_channel.id}},
                upsert=True,
            )
            self.announcement_channel = announcement_channel

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
    async def voting_verdict(self) -> None:
        # Wait until the bot's internal cache is ready
        await self.bot.wait_until_ready()

        # Get the announcements channel
        announcement_channel = await self.get_announcement_channel()
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
                ctx = await self.bot.get_context(message)
                await ctx.invoke(
                    self.bot.get_command("ctf createctf"), ctf_name=event["name"]
                )

                # Send a message with the @everyone mention in the announcements channel
                # with instructions on how to join the CTF
                await announcement_channel.send(
                    f"{announcement_channel.guild.default_role}\n"
                    "A new CTF has been created, you can joing using "
                    f"`{self.bot.command_prefix}ctf join \"{event['name']}\"`"
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
                tasks.loop(count=1)(self.ctf_started_reminder).start(
                    timeleft, general_channel, role
                )

    async def ctf_started_reminder(
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
        if payload.member.id == self.bot.user.id:
            return

        announcement_channel = await self.get_announcement_channel()
        if payload.channel_id == announcement_channel.id:
            message = await announcement_channel.fetch_message(payload.message_id)
            for reaction in message.reactions:
                # Remove all reactions from that user except the one they just added
                if str(reaction) != str(payload.emoji):
                    await message.remove_reaction(reaction.emoji, payload.member)

    @commands.group()
    @commands.guild_only()
    async def ctftime(self, ctx: Context) -> None:
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(
                title=f"Commands group for {self.bot.command_prefix}{ctx.invoked_with}",
                colour=discord.Colour.blue(),
            ).set_thumbnail(url=self.bot.user.avatar_url)

            for command in help_info[ctx.invoked_with]:
                embed.add_field(
                    name=help_info[ctx.invoked_with][command]["usage"].format(
                        self.bot.command_prefix
                    ),
                    value=help_info[ctx.invoked_with][command]["brief"],
                    inline=False,
                )

            await ctx.send(embed=embed)

    @ctftime.command(aliases=help_info["ctftime"]["current"]["aliases"])
    async def current(self, ctx: Context) -> None:
        no_running_events = True
        for event in scrape_current_events():
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
            await ctx.channel.send(embed=embed)

        if no_running_events:
            await ctx.send("No ongoing CTFs for the moment.")

    @ctftime.command(aliases=help_info["ctftime"]["upcoming"]["aliases"])
    async def upcoming(self, ctx: Context, limit: int = None) -> None:
        limit = int(limit) if limit else 3
        query_filter = {"start": {"$gt": int(time.time())}}
        no_upcoming_events = True

        for event in mongo[CTFTIME_EVENTS_COLLECTION].find(query_filter).limit(limit):
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
            await ctx.channel.send(embed=embed)

        if no_upcoming_events:
            await ctx.send("No upcoming CTFs.")

    @ctftime.command(aliases=help_info["ctftime"]["top"]["aliases"])
    async def top(self, ctx: Context, year: int = None) -> None:
        year = (
            year
            if year and year.isdigit() and len(year) == 4
            else str(datetime.today().year)
        )
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
    bot.add_cog(CTFTime(bot))
