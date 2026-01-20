"""Background task for CTF reminders."""

from datetime import timedelta
from typing import TYPE_CHECKING

import config
import discord
from config import GUILD_ID, MIN_PLAYERS
from constants import ChannelNames, Emojis
from discord.ext import tasks
from utils.time import get_local_time

if TYPE_CHECKING:
    from eruditus import Eruditus


def create_ctf_reminder_task(client: "Eruditus") -> tasks.Loop:
    """Create the CTF reminder task.

    Args:
        client: The Discord bot client.

    Returns:
        The configured task loop.
    """

    @tasks.loop(minutes=5, reconnect=True)
    async def ctf_reminder() -> None:
        """Create a CTF for events starting soon and send a reminder."""
        await client.wait_until_ready()

        local_time = get_local_time()
        guild = client.get_guild(GUILD_ID)
        if not guild:
            return

        if config.REMINDER_CHANNEL is None:
            reminder_channel = None
            for channel in guild.text_channels:
                if channel.permissions_for(guild.default_role).read_messages:
                    reminder_channel = channel
                    if ChannelNames.GENERAL in reminder_channel.name:
                        break
        else:
            reminder_channel = client.get_channel(config.REMINDER_CHANNEL)

        for scheduled_event in guild.scheduled_events:
            if (
                scheduled_event.status != discord.EventStatus.scheduled
                or scheduled_event.location.startswith(Emojis.GLOBE)
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
                location=f"{Emojis.GLOBE} {scheduled_event.location}",
                privacy_level=discord.PrivacyLevel.guild_only,
            )

            users = [user async for user in scheduled_event.users()]
            if len(users) < MIN_PLAYERS:
                if reminder_channel:
                    await reminder_channel.send(
                        f"{Emojis.BELL} CTF `{event_name}` starting "
                        f"<t:{scheduled_event.start_time.timestamp():.0f}:R>.\n"
                        f"This CTF was not created automatically because less than"
                        f" {MIN_PLAYERS} players were willing to participate.\n"
                        f"You can still create it manually using `/ctf createctf`."
                    )
                continue

            ctf = await client.create_ctf(event_name, live=False, return_if_exists=True)

            await client.add_event_roles_to_members_and_register(
                guild, ctf, users, scheduled_event
            )

            if reminder_channel:
                await reminder_channel.send(
                    f"{Emojis.BELL} CTF `{ctf['name']}` starting "
                    f"<t:{scheduled_event.start_time.timestamp():.0f}:R>.\n"
                    f"@here you can still use `/ctf join` to participate in case "
                    f"you forgot to hit the `Interested` button of the event."
                )

    return ctf_reminder
