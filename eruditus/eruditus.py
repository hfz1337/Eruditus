"""Eruditus - Discord CTF Helper Bot."""

import logging
import os
from binascii import hexlify
from typing import Any, Optional

import discord

# New module imports
from commands import (
    CTF,
    Bookmark,
    Cipher,
    CTFTime,
    Encoding,
    Help,
    Intro,
    Report,
    Request,
    Revshell,
    Search,
    Syscalls,
    TakeNote,
)
from components.buttons.workon import WorkonButton
from config import GUILD_ID, MIN_PLAYERS, TEAM_EMAIL, TEAM_NAME
from constants import ChannelNames, Emojis
from db.challenge_repository import ChallengeRepository
from db.ctf_repository import CTFRepository
from discord.utils import setup_logging
from platforms import PlatformCTX, match_platform
from tasks import TaskManager, create_error_handler
from tasks.challenge_puller import create_challenge_puller_task
from tasks.ctf_reminder import create_ctf_reminder_task
from tasks.ctftime_leaderboard_tracker import create_ctftime_leaderboard_tracker
from tasks.ctftime_team_tracker import create_ctftime_team_tracker
from tasks.event_creator import create_event_creator_task
from tasks.scoreboard_updater import create_scoreboard_updater
from utils.crypto import derive_colour
from utils.discord import get_ctf_category, get_ctf_general_channel, get_ctf_role

logger = logging.getLogger("eruditus")


class Eruditus(discord.Client):
    """Main Discord bot client for Eruditus.

    This class handles bot initialization, command registration,
    and event processing for the CTF helper bot.
    """

    def __init__(self) -> None:
        """Initialize the Eruditus bot client."""
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        super().__init__(intents=intents)

        self.tree = discord.app_commands.CommandTree(self)
        self.task_manager = TaskManager(self)

        # State for background tasks
        self.challenge_puller_is_running = False
        self.previous_team_info = None
        self.previous_leaderboard = None

        # Repositories
        self._ctf_repo = CTFRepository()
        self._challenge_repo = ChallengeRepository()

    async def create_ctf(
        self, name: str, live: bool = True, return_if_exists: bool = False
    ) -> Optional[dict]:
        """Create a CTF along with its channels and role.

        Args:
            name: CTF name.
            live: True if the CTF is ongoing.
            return_if_exists: Return the CTF object if it exists.

        Returns:
            A dictionary containing the created CTF, or None if it exists.
        """
        if ctf := self._ctf_repo.find_by_name(name):
            return ctf if return_if_exists else None

        guild = self.get_guild(GUILD_ID)

        # Create role
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

        # Create category channel
        category_channel = discord.utils.get(guild.categories, name=name)
        if category_channel is None:
            prefix = Emojis.LIVE if live else Emojis.PENDING
            category_channel = await guild.create_category(
                name=f"{prefix} {name}",
                overwrites=overwrites,
            )

        await guild.create_text_channel(ChannelNames.GENERAL, category=category_channel)
        await guild.create_voice_channel(
            ChannelNames.GENERAL, category=category_channel
        )

        read_only_overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            role: discord.PermissionOverwrite(read_messages=True, send_messages=False),
        }

        bot_cmds_channel = await guild.create_text_channel(
            name=f"{Emojis.ROBOT}-{ChannelNames.BOT_CMDS}",
            category=category_channel,
            overwrites=overwrites,
        )
        credentials_channel = await guild.create_text_channel(
            name=f"{Emojis.KEY}-{ChannelNames.CREDENTIALS}",
            category=category_channel,
            overwrites=read_only_overwrites,
        )
        notes_channel = await guild.create_text_channel(
            name=f"{Emojis.CLIPBOARD}-{ChannelNames.NOTES}",
            category=category_channel,
            overwrites=read_only_overwrites,
        )
        announcement_channel = await guild.create_text_channel(
            name=f"{Emojis.MEGAPHONE}-{ChannelNames.ANNOUNCEMENTS}",
            category=category_channel,
            overwrites=read_only_overwrites,
        )
        solves_channel = await guild.create_text_channel(
            name=f"{Emojis.CELEBRATION}-{ChannelNames.SOLVES}",
            category=category_channel,
            overwrites=read_only_overwrites,
        )
        scoreboard_channel = await guild.create_text_channel(
            name=f"{Emojis.CHART_UP}-{ChannelNames.SCOREBOARD}",
            category=category_channel,
            overwrites=read_only_overwrites,
        )

        ctf = {
            "name": name,
            "archived": False,
            "ended": False,
            "private": False,
            "credentials": {"url": None, "username": None, "password": None},
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
        self._ctf_repo.insert_one(ctf)
        return ctf

    async def _do_ctf_registration(
        self,
        ctf: dict[str, Any],
        guild: discord.Guild,
        event: discord.ScheduledEvent,
    ) -> None:
        """Register a team account on the CTF platform."""
        url = event.location.split(" \u2014 ")[1]
        password = hexlify(os.urandom(32)).decode()

        ctx = PlatformCTX(
            base_url=url,
            args={"username": TEAM_NAME, "password": password, "email": TEAM_EMAIL},
        )
        platform = await match_platform(ctx)
        if platform is None:
            return

        result = await platform.impl.register(ctx)

        if result.success:
            ctf["credentials"]["url"] = url
            ctf["credentials"]["username"] = TEAM_NAME
            ctf["credentials"]["password"] = password
            ctf["credentials"]["token"] = result.token
            ctf["credentials"]["teamToken"] = result.invite

            self._ctf_repo.update_credentials(ctf["_id"], ctf["credentials"])

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

    async def add_event_roles_to_members_and_register(
        self,
        guild: discord.Guild,
        ctf: dict,
        users: list[discord.User],
        event: discord.ScheduledEvent,
    ) -> discord.Role:
        """Add roles to event participants and register on the platform."""
        await self._do_ctf_registration(ctf=ctf, guild=guild, event=event)

        role = discord.utils.get(guild.roles, id=ctf["guild_role"])
        if ctf.get("private"):
            return role

        for user in users:
            member = await guild.fetch_member(user.id)
            await member.add_roles(role)

        return role

    async def setup_hook(self) -> None:
        """Set up commands, views, and background tasks."""
        self._register_commands()
        self._restore_views()
        self._setup_tasks()

    def _register_commands(self) -> None:
        """Register all slash commands."""
        # Global commands
        self.tree.add_command(Help())
        self.tree.add_command(Syscalls())
        self.tree.add_command(Revshell())
        self.tree.add_command(Encoding())
        self.tree.add_command(CTFTime())
        self.tree.add_command(Cipher())
        self.tree.add_command(Report())
        self.tree.add_command(Request())
        self.tree.add_command(Search())

        # Guild-specific commands
        guild_obj = discord.Object(GUILD_ID)
        self.tree.add_command(Bookmark(), guild=guild_obj)
        self.tree.add_command(TakeNote(), guild=guild_obj)
        self.tree.add_command(CTF(), guild=guild_obj)
        self.tree.add_command(Intro(), guild=guild_obj)

    def _restore_views(self) -> None:
        """Restore persistent views (workon buttons)."""
        for challenge in self._challenge_repo.find_unsolved():
            self.add_view(WorkonButton(oid=challenge["_id"]))

    def _setup_tasks(self) -> None:
        """Set up and start background tasks."""
        # Create tasks
        self.create_upcoming_events = create_event_creator_task(self)
        self.ctf_reminder = create_ctf_reminder_task(self)
        self.challenge_puller = create_challenge_puller_task(self)
        self.scoreboard_updater = create_scoreboard_updater(self)
        self.ctftime_team_tracking = create_ctftime_team_tracker(self)
        self.ctftime_leaderboard_tracking = create_ctftime_leaderboard_tracker(self)

        # Register error handlers
        self.create_upcoming_events.error(
            create_error_handler(self.create_upcoming_events)
        )
        self.ctf_reminder.error(create_error_handler(self.ctf_reminder))
        self.challenge_puller.error(create_error_handler(self.challenge_puller))
        self.scoreboard_updater.error(create_error_handler(self.scoreboard_updater))
        self.ctftime_team_tracking.error(
            create_error_handler(self.ctftime_team_tracking)
        )
        self.ctftime_leaderboard_tracking.error(
            create_error_handler(self.ctftime_leaderboard_tracking)
        )

        # Start all tasks
        self.create_upcoming_events.start()
        self.ctf_reminder.start()
        self.challenge_puller.start()
        self.scoreboard_updater.start()
        self.ctftime_team_tracking.start()
        self.ctftime_leaderboard_tracking.start()

    async def on_ready(self) -> None:
        """Handle bot ready event."""
        for guild in self.guilds:
            logger.info("%s connected to %s", self.user, guild)

        await self.tree.sync()
        await self.tree.sync(guild=discord.Object(id=GUILD_ID))
        await self.change_presence(activity=discord.Game(name="/help"))

    async def on_guild_join(self, guild: discord.Guild) -> None:
        """Handle guild join event."""
        logger.info("%s joined %s!", self.user, guild)

    async def on_guild_remove(self, guild: discord.Guild) -> None:
        """Handle guild remove event."""
        logger.info("%s left %s.", self.user, guild)

    async def on_scheduled_event_update(
        self, before: discord.ScheduledEvent, after: discord.ScheduledEvent
    ) -> None:
        """Handle scheduled event status changes."""
        guild = self.get_guild(GUILD_ID)
        event_name = after.name

        # Event started
        if (
            before.status == discord.EventStatus.scheduled
            and after.status == discord.EventStatus.active
        ):
            users = [user async for user in after.users()]
            if len(users) < MIN_PLAYERS:
                return

            ctf = await self.create_ctf(after.name, live=True, return_if_exists=True)
            role = await self.add_event_roles_to_members_and_register(
                guild, ctf, users, after
            )

            ctf_general_channel = get_ctf_general_channel(guild, ctf)
            if ctf_general_channel:
                await ctf_general_channel.send(
                    f"{role.mention} has started!\n"
                    f"Get to work now {Emojis.SWORD} {Emojis.GUN}"
                )

            self.challenge_puller.restart()

            category_channel = get_ctf_category(guild, ctf)
            if category_channel:
                await category_channel.edit(
                    name=category_channel.name.replace(Emojis.PENDING, Emojis.LIVE)
                )

        # Event ended
        elif (
            before.status == discord.EventStatus.active
            and after.status == discord.EventStatus.ended
        ):
            ctf = self._ctf_repo.find_by_name(event_name)
            if ctf is None:
                return

            role = get_ctf_role(guild, ctf)
            ctf_general_channel = get_ctf_general_channel(guild, ctf)
            if ctf_general_channel and role:
                await ctf_general_channel.send(
                    f"{Emojis.ENDED} {role.mention} time is up! The CTF has ended."
                )

            self._ctf_repo.set_ended(ctf["_id"])

            category_channel = get_ctf_category(guild, ctf)
            if category_channel:
                await category_channel.edit(
                    name=category_channel.name.replace(Emojis.LIVE, Emojis.ENDED)
                )


if __name__ == "__main__":
    setup_logging()
    client = Eruditus()
    client.run(os.getenv("DISCORD_TOKEN"))
