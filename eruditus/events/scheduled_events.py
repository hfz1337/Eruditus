"""Handlers for Discord scheduled event updates."""

import discord
from constants import ChannelNames, Emojis
from db.ctf_repository import CTFRepository

_ctf_repo = CTFRepository()


async def handle_scheduled_event_start(
    guild: discord.Guild,
    ctf: dict,
    role: discord.Role,
) -> None:
    """Handle when a scheduled CTF event starts.

    Args:
        guild: The Discord guild.
        ctf: The CTF document.
        role: The CTF role.
    """
    ctf_general_channel = discord.utils.get(
        guild.text_channels,
        category_id=ctf["guild_category"],
        name=ChannelNames.GENERAL,
    )
    if ctf_general_channel:
        await ctf_general_channel.send(
            f"{role.mention} has started!\nGet to work now {Emojis.SWORD} {Emojis.GUN}"
        )

    category_channel = discord.utils.get(guild.categories, id=ctf["guild_category"])
    if category_channel:
        await category_channel.edit(
            name=category_channel.name.replace(Emojis.PENDING, Emojis.LIVE)
        )


async def handle_scheduled_event_end(
    guild: discord.Guild,
    event_name: str,
) -> None:
    """Handle when a scheduled CTF event ends.

    Args:
        guild: The Discord guild.
        event_name: The name of the event that ended.
    """
    ctf = _ctf_repo.find_by_name(event_name)
    if ctf is None:
        return

    role = discord.utils.get(guild.roles, id=ctf["guild_role"])
    ctf_general_channel = discord.utils.get(
        guild.text_channels,
        category_id=ctf["guild_category"],
        name=ChannelNames.GENERAL,
    )
    if ctf_general_channel and role:
        await ctf_general_channel.send(
            f"{Emojis.ENDED} {role.mention} time is up! The CTF has ended."
        )

    _ctf_repo.set_ended(ctf["_id"])

    category_channel = discord.utils.get(guild.categories, id=ctf["guild_category"])
    if category_channel:
        await category_channel.edit(
            name=category_channel.name.replace(Emojis.LIVE, Emojis.ENDED)
        )
