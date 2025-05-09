import logging
import os
import traceback
from binascii import hexlify
from datetime import datetime, timedelta
from typing import Any, Union

import aiohttp
import discord
from bson import ObjectId
from discord.ext import tasks
from discord.utils import setup_logging

import config
from app_commands.bookmark import Bookmark
from app_commands.cipher import Cipher
from app_commands.ctf import CTF
from app_commands.ctftime import CTFTime
from app_commands.encoding import Encoding
from app_commands.help import Help
from app_commands.intro import Intro
from app_commands.report import Report
from app_commands.request import Request
from app_commands.revshell import Revshell
from app_commands.search import Search
from app_commands.syscalls import Syscalls
from app_commands.takenote import TakeNote
from config import (
    CHALLENGE_COLLECTION,
    CTF_COLLECTION,
    CTFTIME_LEADERBOARD_CHANNEL,
    CTFTIME_TEAM_ID,
    CTFTIME_TRACKING_CHANNEL,
    DBNAME,
    GUILD_ID,
    MAX_CONTENT_SIZE,
    MIN_PLAYERS,
    MONGO,
    TEAM_EMAIL,
    TEAM_NAME,
)
from lib.ctftime.events import create_discord_events
from lib.ctftime.leaderboard import get_ctftime_leaderboard
from lib.ctftime.teams import get_ctftime_team_info
from lib.ctftime.types import CTFTimeDiffType
from lib.discord_util import get_challenge_category_channel, send_scoreboard
from lib.platforms import PlatformCTX, match_platform
from lib.util import (
    country_name,
    derive_colour,
    get_challenge_info,
    get_ctf_info,
    get_local_time,
    sanitize_channel_name,
    truncate,
)
from msg_components.buttons.workon import WorkonButton


class Eruditus(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        super().__init__(intents=intents)

        self.tree = discord.app_commands.CommandTree(self)
        self.challenge_puller_is_running = False
        self.previous_team_info = None
        self.previous_leaderboard = None

    async def create_ctf(
        self, name: str, live: bool = True, return_if_exists: bool = False
    ) -> Union[dict, None]:
        """Create a CTF along with its channels and role.

        Args:
            name: CTF name.
            live: True if the CTF is ongoing.
            return_if_exists: Causes the function to return the CTF object instead of
                None in case it exists.

        Returns:
            A dictionary containing information about the created CTF, or None if the
            CTF already exists.
        """
        # Check if the CTF already exists (case insensitive).
        if ctf := get_ctf_info(name=name):
            if return_if_exists:
                return ctf
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

        bot_cmds_channel = await guild.create_text_channel(
            name="🤖-bot-cmds",
            category=category_channel,
            overwrites={
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                role: discord.PermissionOverwrite(read_messages=True),
            },
        )
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
            "ended": False,
            "private": False,
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
                "bot-cmds": bot_cmds_channel.id,
            },
        }
        MONGO[DBNAME][CTF_COLLECTION].insert_one(ctf)
        return ctf

    async def setup_hook(self) -> None:
        # Register commands.
        self.tree.add_command(Help())
        self.tree.add_command(Syscalls())
        self.tree.add_command(Revshell())
        self.tree.add_command(Encoding())
        self.tree.add_command(CTFTime())
        self.tree.add_command(Cipher())
        self.tree.add_command(Report())
        self.tree.add_command(Request())
        self.tree.add_command(Search())
        self.tree.add_command(Bookmark(), guild=discord.Object(GUILD_ID))
        self.tree.add_command(TakeNote(), guild=discord.Object(GUILD_ID))
        self.tree.add_command(CTF(), guild=discord.Object(GUILD_ID))
        self.tree.add_command(Intro(), guild=discord.Object(GUILD_ID))

        # Restore `workon` buttons.
        for challenge in MONGO[DBNAME][CHALLENGE_COLLECTION].find({"solved": False}):
            self.add_view(WorkonButton(oid=challenge["_id"]))

        self.create_upcoming_events.start()
        self.ctf_reminder.start()
        self.scoreboard_updater.start()
        self.challenge_puller.start()
        self.ctftime_team_tracking.start()
        self.ctftime_leaderboard_tracking.start()

    async def on_ready(self) -> None:
        for guild in self.guilds:
            logger.info("%s connected to %s", self.user, guild)

        # Sync global and guild specific commands.
        await self.tree.sync()
        await self.tree.sync(guild=discord.Object(id=GUILD_ID))

        await self.change_presence(activity=discord.Game(name="/help"))

    async def on_guild_join(self, guild: discord.Guild) -> None:
        logger.info("%s joined %s!", self.user, guild)

    async def on_guild_remove(self, guild: discord.Guild) -> None:
        logger.info("%s left %s.", self.user, guild)

    @staticmethod
    async def _do_ctf_registration(
        ctf: dict[str, Any],
        guild: discord.Guild,
        event: discord.ScheduledEvent,
    ) -> None:
        # Register a team account if it's a supported platform.
        url = event.location.split(" — ")[1]
        password = hexlify(os.urandom(32)).decode()

        # Match the platform
        ctx = PlatformCTX(
            base_url=url,
            args={"username": TEAM_NAME, "password": password, "email": TEAM_EMAIL},
        )
        platform = await match_platform(ctx)
        if platform is None:
            # Unsupported platform
            return

        result = await platform.register(ctx)

        if result.success:
            # Add credentials.
            ctf["credentials"]["url"] = url
            ctf["credentials"]["username"] = TEAM_NAME
            ctf["credentials"]["password"] = password
            ctf["credentials"]["token"] = result.token
            ctf["credentials"]["teamToken"] = result.invite

            MONGO[DBNAME][CTF_COLLECTION].update_one(
                {"_id": ctf["_id"]},
                {"$set": {"credentials": ctf["credentials"]}},
            )

            creds_channel = discord.utils.get(
                guild.text_channels, id=ctf["guild_channels"]["credentials"]
            )
            message = (
                f"CTF platform: {url}\n"
                "```yaml\n"
                f"Username: {TEAM_NAME}\n"
                f"Password: {password}\n"
            )

            if result.invite is not None:
                message += f"Invite: {result.invite}\n"

            message += "```"

            await creds_channel.purge()
            await creds_channel.send(message)

    @classmethod
    async def add_event_roles_to_members_and_register(
        cls,
        guild: discord.Guild,
        ctf: dict,
        users: list[discord.User],
        event: discord.ScheduledEvent,
    ) -> discord.Role:
        # Register to the CTF.
        await cls._do_ctf_registration(ctf=ctf, guild=guild, event=event)

        role = discord.utils.get(guild.roles, id=ctf["guild_role"])
        if ctf.get("private"):
            return role

        for user in users:
            member = await guild.fetch_member(user.id)
            await member.add_roles(role)

        return role

    async def on_scheduled_event_update(
        self, before: discord.ScheduledEvent, after: discord.ScheduledEvent
    ) -> None:
        # The bot is supposed to be part of a single guild.
        guild = self.get_guild(GUILD_ID)

        event_name = after.name
        # If an event started (status changes from scheduled to active).
        if (
            before.status == discord.EventStatus.scheduled
            and after.status == discord.EventStatus.active
        ):
            # Create the CTF if it wasn't already created and enough people are willing
            # to play it.
            users = [user async for user in after.users()]
            if len(users) < MIN_PLAYERS:
                return
            ctf = await self.create_ctf(after.name, live=True, return_if_exists=True)

            role = await self.add_event_roles_to_members_and_register(
                guild, ctf, users, after
            )

            # Ping all participants.
            ctf_general_channel = discord.utils.get(
                guild.text_channels,
                category_id=ctf["guild_category"],
                name="general",
            )
            await ctf_general_channel.send(
                f"{role.mention} has started!\nGet to work now ⚔️ 🔪 😠 🔨 ⚒️"
            )

            # Pull challenges without waiting for scheduled task to execute.
            self.challenge_puller.restart()

            # Substitute the ⏰ in the category channel name with a 🔴 to say that
            # we're live.
            category_channel = discord.utils.get(
                guild.categories, id=ctf["guild_category"]
            )
            await category_channel.edit(name=category_channel.name.replace("⏰", "🔴"))

        # If an event ended (status changes from active to ended/completed).
        elif (
            before.status == discord.EventStatus.active
            and after.status == discord.EventStatus.ended
        ):
            # Ping players that the CTF ended.
            ctf = get_ctf_info(name=event_name)
            if ctf is None:
                return

            # Ping all participants.
            role = discord.utils.get(guild.roles, id=ctf["guild_role"])
            ctf_general_channel = discord.utils.get(
                guild.text_channels,
                category_id=ctf["guild_category"],
                name="general",
            )
            await ctf_general_channel.send(
                f"🏁 {role.mention} time is up! The CTF has ended."
            )

            # Update status of the CTF.
            MONGO[DBNAME][CTF_COLLECTION].update_one(
                {"_id": ctf["_id"]}, {"$set": {"ended": True}}
            )

            # Substitue the 🔴 in the category channel name with a 🏁 to say that
            # the CTF ended.
            category_channel = discord.utils.get(
                guild.categories, id=ctf["guild_category"]
            )
            await category_channel.edit(name=category_channel.name.replace("🔴", "🏁"))

    @tasks.loop(minutes=5, reconnect=True)
    async def ctf_reminder(self) -> None:
        """Create a CTF for events starting soon and send a reminder."""
        # Wait until the bot's internal cache is ready.
        await self.wait_until_ready()

        # Timezone aware local time.
        local_time = get_local_time()

        # The bot is supposed to be part of a single guild.
        guild = self.get_guild(GUILD_ID)

        if config.REMINDER_CHANNEL is None:
            # Find a public channel where we can send our reminders.
            reminder_channel = None
            for channel in guild.text_channels:
                if channel.permissions_for(guild.default_role).read_messages:
                    reminder_channel = channel
                    if "general" in reminder_channel.name:
                        break
        else:
            reminder_channel = self.get_channel(config.REMINDER_CHANNEL)

        for scheduled_event in guild.scheduled_events:
            if (
                scheduled_event.status != discord.EventStatus.scheduled
                or scheduled_event.location.startswith("🌐")
            ):
                continue

            remaining_time = scheduled_event.start_time - local_time
            if remaining_time > timedelta(hours=1):
                continue

            event_name = scheduled_event.name
            await scheduled_event.edit(
                name=event_name,
                description=scheduled_event.description,
                start_time=scheduled_event.start_time,
                end_time=scheduled_event.end_time,
                entity_type=scheduled_event.entity_type,
                location=f"🌐 {scheduled_event.location}",
                privacy_level=discord.PrivacyLevel.guild_only,
            )

            # Ignore this event if not too many people are interested in it.
            users = [user async for user in scheduled_event.users()]
            if len(users) < MIN_PLAYERS:
                if reminder_channel:
                    await reminder_channel.send(
                        f"🔔 CTF `{event_name}` starting "
                        f"<t:{scheduled_event.start_time.timestamp():.0f}:R>.\n"
                        f"This CTF was not created automatically because less than"
                        f" {MIN_PLAYERS} players were willing to participate.\n"
                        f"You can still create it manually using `/ctf createctf`."
                    )
                continue

            # If a CTF is starting soon, we create it if it wasn't created yet.
            ctf = await self.create_ctf(event_name, live=False, return_if_exists=True)

            await self.add_event_roles_to_members_and_register(
                guild, ctf, users, scheduled_event
            )

            # Send a reminder that the CTF is starting soon.
            if reminder_channel:
                await reminder_channel.send(
                    f"🔔 CTF `{ctf['name']}` starting "
                    f"<t:{scheduled_event.start_time.timestamp():.0f}:R>.\n"
                    f"@here you can still use `/ctf join` to participate in case "
                    f"you forgot to hit the `Interested` button of the event."
                )

    @tasks.loop(hours=3, reconnect=True)
    async def create_upcoming_events(self) -> None:
        """Create a Scheduled Event for each upcoming CTF competition."""
        # Wait until the bot's internal cache is ready.
        await self.wait_until_ready()
        await create_discord_events(
            guild=self.get_guild(GUILD_ID),
            current_loop=self.create_upcoming_events.current_loop,
        )

    @tasks.loop(minutes=2, reconnect=True)
    async def challenge_puller(self) -> None:
        """Periodically pull challenges for all running CTFs."""
        self.challenge_puller_is_running = True

        # Wait until the bot's internal cache is ready.
        await self.wait_until_ready()

        # The bot is supposed to be part of a single guild.
        guild = self.get_guild(GUILD_ID)

        for ctf in MONGO[DBNAME][CTF_COLLECTION].find({"ended": False}):
            url = ctf["credentials"]["url"]

            if url is None:
                continue

            category_channel = discord.utils.get(
                guild.categories, id=ctf["guild_category"]
            )

            # Match the platform
            ctx = PlatformCTX.from_credentials(ctf["credentials"])
            try:
                platform = await match_platform(ctx)
            except aiohttp.ClientError:
                continue

            if platform is None:
                # Unsupported platform
                continue

            async for challenge in platform.pull_challenges(ctx):
                # Skip solved challenges.
                if challenge.solved_by_me:
                    continue

                # Avoid having duplicate categories when people mix up upper/lower case
                # or add unnecessary spaces at the beginning or the end.
                challenge.category = challenge.category.title().strip()

                # Check if challenge was already created.
                if get_challenge_info(
                    id=challenge.id, name=challenge.name, category=challenge.category
                ):
                    continue

                # Send challenge information in its respective thread.
                description = (
                    "\n".join(
                        (
                            challenge.description,
                            (
                                f"`{challenge.connection_info}`"
                                if challenge.connection_info is not None
                                else ""
                            ),
                        )
                    )
                    or "No description."
                )
                tags = ", ".join(challenge.tags or []) or "No tags."

                # Format file information.
                files = []
                for file in challenge.files:
                    if file.name is not None:
                        hyperlink = f"[{file.name}]({file.url})"
                    else:
                        hyperlink = file.url

                    files.append(hyperlink)

                files_str = "No files."
                if len(files) > 0:
                    files_str = "\n- ".join(files)
                files_str = "\n- " + files_str

                # Try to fetch images if any.
                img_attachments = []
                img_urls = []
                for image in challenge.images or []:
                    # If the image is internal to the platform itself, it may require
                    # authentication.
                    if image.url.startswith(ctx.base_url):
                        raw_image = await platform.fetch(ctx, image.url)
                        if raw_image is None:
                            continue
                        attachment = discord.File(raw_image, filename=image.name)
                        img_attachments.append(attachment)
                    # Otherwise, if it's external, we don't need to fetch it ourselves,
                    # we can just send the URL as is.
                    else:
                        img_urls.append(image.url)

                embed = discord.Embed(
                    title=f"{challenge.name} - {challenge.value} points",
                    description=truncate(
                        f"**Category:** {challenge.category}\n"
                        f"**Description:** {description}\n"
                        f"**Files:** {files_str}\n"
                        f"**Tags:** {tags}",
                        max_len=4096,
                    ),
                    colour=discord.Colour.blue(),
                    timestamp=datetime.now(),
                )

                # Add a single image to the embed if there are external images.
                if img_urls:
                    embed.set_image(url=img_urls.pop(0))

                # Create a channel for the challenge category if it doesn't exist.
                text_channel = await get_challenge_category_channel(
                    guild, category_channel, challenge.category
                )

                # Create a private thread for the challenge.
                thread_name = sanitize_channel_name(challenge.name)
                challenge_thread = await text_channel.create_thread(
                    name=f"❌-{thread_name}", invitable=False
                )

                # Send out challenge information.
                message = await challenge_thread.send(embed=embed)

                # Send remaining images if any.
                for img_url in img_urls:
                    await challenge_thread.send(content=img_url)
                if img_attachments:
                    await challenge_thread.send(files=img_attachments)

                # Pin the challenge info message.
                await message.pin()

                # Create an ObjectID for the challenge document.
                challenge_oid = ObjectId()

                # Announce that the challenge was added.
                announcements_channel = discord.utils.get(
                    guild.text_channels,
                    id=ctf["guild_channels"]["announcements"],
                )
                role = discord.utils.get(guild.roles, id=ctf["guild_role"])

                embed = discord.Embed(
                    title="🔔 New challenge created!",
                    description=(
                        f"**Challenge name:** {challenge.name}\n"
                        f"**Category:** {challenge.category}\n\n"
                        f"Use `/ctf workon {challenge.name}` or the button to join."
                        f"\n{role.mention}"
                    ),
                    colour=discord.Colour.dark_gold(),
                    timestamp=datetime.now(),
                )
                announcement = await announcements_channel.send(
                    embed=embed, view=WorkonButton(oid=challenge_oid)
                )

                # Add challenge to the database.
                MONGO[DBNAME][CHALLENGE_COLLECTION].insert_one(
                    {
                        "_id": challenge_oid,
                        "id": challenge.id,
                        "name": challenge.name,
                        "category": challenge.category,
                        "thread": challenge_thread.id,
                        "solved": False,
                        "blooded": False,
                        "players": [],
                        "announcement": announcement.id,
                        "solve_time": None,
                        "solve_announcement": None,
                    }
                )

                # Add reference to the newly created challenge.
                ctf["challenges"].append(challenge_oid)
                MONGO[DBNAME][CTF_COLLECTION].update_one(
                    {"_id": ctf["_id"]}, {"$set": {"challenges": ctf["challenges"]}}
                )

                await text_channel.edit(
                    name=text_channel.name.replace("💤", "🔄").replace("🎯", "🔄")
                )

        self.challenge_puller_is_running = False

    @tasks.loop(minutes=1, reconnect=True)
    async def scoreboard_updater(self) -> None:
        """Periodically update the scoreboard for all running CTFs."""
        # Wait until the bot's internal cache is ready.
        await self.wait_until_ready()

        # The bot is supposed to be part of a single guild.
        guild = self.get_guild(GUILD_ID)

        for ctf in MONGO[DBNAME][CTF_COLLECTION].find({"ended": False}):
            await send_scoreboard(ctf, guild=guild)

    @tasks.loop(minutes=15, reconnect=True)
    async def ctftime_team_tracking(self) -> None:
        # Wait until the bot's internal cache is ready.
        await self.wait_until_ready()

        # Disable the feature if some of the related config vars are missing.
        if not CTFTIME_TRACKING_CHANNEL or not CTFTIME_TEAM_ID:
            self.ctftime_team_tracking.stop()
            return

        # Find the channel.
        guild = self.get_guild(GUILD_ID)
        channel = guild.get_channel(CTFTIME_TRACKING_CHANNEL) if guild else None
        if not channel:
            logger.error(
                "Unable to find the CTFtime tracking channel, make sure the channel "
                "ID is valid."
            )
            return

        # Request the CTFtime team info
        team_info = await get_ctftime_team_info(CTFTIME_TEAM_ID)
        if not team_info:
            return

        # If we didn't have a previous state to compare with, we save this one and bail
        # out.
        if not self.previous_team_info:
            self.previous_team_info = team_info
            return

        # Detect changes and post them into the relevant channel.
        msg_fmt = "{} {} changed from {} to {}"
        for update_type in (diff := self.previous_team_info - team_info):
            match update_type:
                case CTFTimeDiffType.OVERALL_POINTS_UPDATE:
                    if (
                        abs(
                            self.previous_team_info.overall_points
                            - team_info.overall_points
                        )
                        < 1
                    ):
                        continue
                    decreased = (
                        self.previous_team_info.overall_points
                        > team_info.overall_points
                    )
                    msg = msg_fmt.format(
                        "📉" if decreased else "📈",
                        "Overall points",
                        self.previous_team_info.overall_points,
                        team_info.overall_points,
                    )
                    await channel.send(msg)

                case CTFTimeDiffType.OVERALL_PLACE_UPDATE:
                    msg = msg_fmt.format(
                        "🌎",
                        "Global position",
                        self.previous_team_info.overall_rating_place,
                        team_info.overall_rating_place,
                    )
                    await channel.send(msg)

                case CTFTimeDiffType.COUNTRY_PLACE_UPDATE:
                    msg = msg_fmt.format(
                        f":flag_{team_info.country_code.lower()}:",
                        "Country position",
                        self.previous_team_info.country_place,
                        team_info.country_place,
                    )
                    await channel.send(msg)

                case CTFTimeDiffType.EVENT_UPDATE:
                    msg = (
                        "There was an update to the `{}` event:\n"
                        "```diff\n"
                        f"  {'Place'} {'Event':<30} {'CTF points':<15} "
                        f"{'Rating points':<15}\n"
                        "- {} {} {} {}\n"
                        "+ {} {} {} {}\n"
                        f"```"
                    )
                    for event_diff in diff[CTFTimeDiffType.EVENT_UPDATE]:
                        if (
                            abs(
                                event_diff[0].rating_points
                                - event_diff[1].rating_points
                            )
                            < 1
                        ):
                            continue
                        await channel.send(
                            msg.format(
                                event_diff[0].event_name,
                                f"{event_diff[0].place:<5}",
                                f"{event_diff[0].event_name:<30}",
                                f"{event_diff[0].ctf_points:<15.4f}",
                                f"{event_diff[0].rating_points:<15.4f}",
                                f"{event_diff[1].place:<5}",
                                f"{event_diff[1].event_name:<30}",
                                f"{event_diff[1].ctf_points:<15.4f}",
                                f"{event_diff[1].rating_points:<15.4f}",
                            )
                        )

        self.previous_team_info = team_info

    @tasks.loop(minutes=15, reconnect=True)
    async def ctftime_leaderboard_tracking(self) -> None:
        # Wait until the bot's internal cache is ready.
        await self.wait_until_ready()

        # Disable the feature if some of the related config vars are missing.
        if not CTFTIME_LEADERBOARD_CHANNEL:
            self.ctftime_leaderboard_tracking.stop()
            return

        # Find the channel.
        guild = self.get_guild(GUILD_ID)
        channel = guild.get_channel(CTFTIME_LEADERBOARD_CHANNEL) if guild else None
        if not channel:
            logger.error(
                "Unable to find the CTFtime leaderboard channel, make sure the channel"
                " ID is valid."
            )
            return

        # Request the CTFtime leaderboard.
        leaderboard = await get_ctftime_leaderboard(n=50)
        if not leaderboard:
            return

        first_run = False
        if not self.previous_leaderboard:
            first_run = True
            self.previous_leaderboard = leaderboard

        # Detect changes and post them into the relevant channel.
        head = (
            f"  📊 {'Rank':<10} {'Country':<53} {'Points':<15} {'Events':<10} Name\n\n"
        )
        team_ids = list(self.previous_leaderboard.keys())
        chunks, chunk, update = [], head, False
        for index, (team_id, row) in enumerate(leaderboard.items()):
            if team_id not in self.previous_leaderboard or index < team_ids.index(
                team_id
            ):
                emoji = "🔼"
                update = True
            elif index == team_ids.index(team_id):
                emoji = "➖"
            else:
                emoji = "🔻"
                update = True

            diff = (
                {"🔼": "+", "🔻": "-", "➖": "+"}[emoji]
                if team_id == CTFTIME_TEAM_ID
                else " "
            )
            country = country_name(row.country_code or "") or ""
            line = (
                f"{diff} {emoji} {row.position:>4}       {country:<45} "
                f"{row.points:>17.4f} {row.events:>12}     {row.team_name}\n"
            )
            if len(chunk) + len(line) < MAX_CONTENT_SIZE - 11:  # -11 for the formatting
                chunk += line
            else:
                chunks.append(chunk)
                chunk = head + line

        chunks.append(chunk)

        self.previous_leaderboard = leaderboard
        if not update and not first_run:
            return

        await channel.purge()
        for msg in chunks:
            await channel.send(f"```diff\n{msg}```", silent=True)

    @create_upcoming_events.error
    async def create_upcoming_events_err_handler(self, _: Exception) -> None:
        traceback.print_exc()
        self.create_upcoming_events.restart()

    @ctf_reminder.error
    async def ctf_reminder_err_handler(self, _: Exception) -> None:
        traceback.print_exc()
        self.ctf_reminder.restart()

    @scoreboard_updater.error
    async def scoreboard_updater_err_handler(self, _: Exception) -> None:
        traceback.print_exc()
        self.scoreboard_updater.restart()

    @challenge_puller.error
    async def challenge_puller_err_handler(self, _: Exception) -> None:
        traceback.print_exc()
        self.challenge_puller.restart()

    @ctftime_team_tracking.error
    async def ctftime_team_tracking_err_handler(self, _: Exception) -> None:
        traceback.print_exc()
        self.ctftime_team_tracking.restart()

    @ctftime_leaderboard_tracking.error
    async def ctftime_leaderboard_tracking_err_handler(self, _: Exception) -> None:
        traceback.print_exc()
        self.ctftime_leaderboard_tracking.restart()


if __name__ == "__main__":
    setup_logging()
    logger = logging.getLogger("eruditus")
    client = Eruditus()
    client.run(os.getenv("DISCORD_TOKEN"))
