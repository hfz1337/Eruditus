"""Discord-specific utilities."""

import re
from typing import Optional

import discord
from constants import (
    DEFAULT_AUTO_ARCHIVE_DURATION,
    CategoryPrefixes,
    ChannelNames,
    Emojis,
)
from db.challenge_repository import ChallengeRepository
from db.ctf_repository import CTFRepository
from discord import InteractionResponseType
from utils.formatting import sanitize_channel_name

_ctf_repo = CTFRepository()
_challenge_repo = ChallengeRepository()


# =============================================================================
# CTF Helper Functions - Common discord.utils.get patterns
# =============================================================================


def get_ctf_channel(
    guild: discord.Guild, ctf: dict, channel_type: str
) -> Optional[discord.TextChannel]:
    """Get a specific channel from a CTF's guild_channels.

    Args:
        guild: The Discord guild.
        ctf: The CTF document.
        channel_type: The channel type (announcements, credentials, scoreboard,
            solves, notes, bot-cmds).

    Returns:
        The text channel or None if not found.
    """
    channel_id = ctf.get("guild_channels", {}).get(channel_type)
    if channel_id is None:
        return None
    return discord.utils.get(guild.text_channels, id=channel_id)


def get_ctf_role(guild: discord.Guild, ctf: dict) -> Optional[discord.Role]:
    """Get the role associated with a CTF.

    Args:
        guild: The Discord guild.
        ctf: The CTF document.

    Returns:
        The CTF role or None if not found.
    """
    return discord.utils.get(guild.roles, id=ctf.get("guild_role"))


def get_ctf_category(
    guild: discord.Guild, ctf: dict
) -> Optional[discord.CategoryChannel]:
    """Get the category channel for a CTF.

    Args:
        guild: The Discord guild.
        ctf: The CTF document.

    Returns:
        The category channel or None if not found.
    """
    return discord.utils.get(guild.categories, id=ctf.get("guild_category"))


def get_ctf_general_channel(
    guild: discord.Guild, ctf: dict
) -> Optional[discord.TextChannel]:
    """Get the general channel for a CTF.

    Args:
        guild: The Discord guild.
        ctf: The CTF document.

    Returns:
        The general text channel or None if not found.
    """
    return discord.utils.get(
        guild.text_channels,
        category_id=ctf.get("guild_category"),
        name=ChannelNames.GENERAL,
    )


def get_challenge_thread(
    guild: discord.Guild, challenge: dict
) -> Optional[discord.Thread]:
    """Get the thread associated with a challenge.

    Args:
        guild: The Discord guild.
        challenge: The challenge document.

    Returns:
        The challenge thread or None if not found.
    """
    return discord.utils.get(guild.threads, id=challenge.get("thread"))


def is_deferred(interaction: discord.Interaction) -> bool:
    """Check whether an interaction was deferred previously.

    Args:
        interaction: The Discord interaction.

    Returns:
        True if the interaction was deferred.
    """
    return interaction.response.type in {
        InteractionResponseType.deferred_channel_message,
        InteractionResponseType.deferred_message_update,
    }


async def parse_member_mentions(
    interaction: discord.Interaction, members: str
) -> list[discord.Member]:
    """Extract Discord members mentioned in a string.

    Args:
        interaction: The Discord interaction.
        members: A string containing member mentions.

    Returns:
        A list of Discord member objects.
    """
    result = []
    for member_id in re.findall(r"<@!?([0-9]{15,20})>", members):
        member = await interaction.guild.fetch_member(int(member_id))
        if member:
            result.append(member)
    return result


async def parse_challenge_solvers(
    interaction: discord.Interaction, challenge: dict, members: Optional[str] = None
) -> list[str]:
    """Return a list of users who contributed in solving a challenge.

    Args:
        interaction: The Discord interaction.
        challenge: The challenge document.
        members: A string containing member mentions of those who contributed.

    Returns:
        A list of user names.
    """
    if interaction.user.name not in challenge["players"]:
        challenge["players"].append(interaction.user.name)

    additional_members = set()
    if members:
        parsed = await parse_member_mentions(interaction, members)
        additional_members = {m.name for m in parsed}

    return list({interaction.user.name} | additional_members)


def make_form_field_config(name: str, config: dict) -> dict:
    """Generate configuration for a form field.

    Args:
        name: The field name (e.g., username, password, etc.).
        config: The form configuration (label, placeholder, etc.), for a full list, see
            the arguments of `discord.ui.TextInput`.

    Returns:
        A dictionary containing the field configuration.
    """
    max_length = 128
    match name:
        case "email":
            label, placeholder = "Email", "Enter your email..."
        case "username":
            label, placeholder = "Username", "Enter your username..."
        case "password":
            label, placeholder = "Password", "Enter your password..."
        case "invite":
            label, placeholder, max_length = (
                "Invite link",
                "Enter your team invite URL...",
                512,
            )
        case "token":
            label, placeholder, max_length = (
                "Token",
                "Enter your team token...",
                256,
            )
        case _:
            label, placeholder, max_length = ("Unknown field", "Unknown field", 128)

    return {
        "label": config.get("label", label),
        "placeholder": config.get("placeholder", placeholder),
        "required": config.get("required", True),
        "max_length": config.get("max_length", max_length),
        "style": config.get("style", discord.TextStyle.short),
    }


async def get_challenge_category_channel(
    guild: discord.Guild, ctf_category_channel: discord.CategoryChannel, category: str
) -> discord.TextChannel:
    """Retrieve the text channel associated to a challenge category or create it.

    Args:
        guild: The Discord guild object.
        ctf_category_channel: The CTF category channel.
        category: The challenge category.

    Returns:
        The text channel associated to the CTF category.
    """
    channel_name = sanitize_channel_name(category)

    for prefix in CategoryPrefixes.ALL:
        if text_channel := discord.utils.get(
            guild.text_channels,
            category=ctf_category_channel,
            name=f"{prefix}-{channel_name}",
        ):
            return text_channel

    return await guild.create_text_channel(
        name=f"{Emojis.ACTIVE}-{channel_name}",
        category=ctf_category_channel,
        default_auto_archive_duration=DEFAULT_AUTO_ARCHIVE_DURATION,
    )


async def mark_if_maxed(text_channel: discord.TextChannel, category: str) -> None:
    """Indicate that a CTF category is maxed in case all its challenges are solved.

    Args:
        text_channel: The text channel associated to the CTF category.
        category: The CTF category.
    """
    challenges = _challenge_repo.find_by_category(category)
    if any(not challenge["solved"] for challenge in challenges):
        return

    if text_channel.name.startswith(Emojis.ACTIVE):
        await text_channel.edit(
            name=text_channel.name.replace(Emojis.ACTIVE, Emojis.MAXED)
        )


async def update_category_status(
    text_channel: discord.TextChannel, from_status: str, to_status: str
) -> None:
    """Update a category channel's status emoji prefix.

    Args:
        text_channel: The text channel to update.
        from_status: The current status emoji.
        to_status: The new status emoji.
    """
    if text_channel.name.startswith(from_status):
        await text_channel.edit(name=text_channel.name.replace(from_status, to_status))


async def add_challenge_worker(
    challenge_thread: discord.Thread, challenge: dict, member: discord.Member
) -> None:
    """Add a member to the list of people currently working on a challenge.

    Args:
        challenge_thread: The thread associated to the CTF challenge.
        challenge: The challenge document.
        member: The member to be added.
    """
    challenge["players"].append(member.name)
    _challenge_repo.set_players(challenge["_id"], challenge["players"])
    await challenge_thread.add_user(member)


async def remove_challenge_worker(
    challenge_thread: discord.Thread,
    challenge: dict,
    member: discord.Member,
) -> None:
    """Remove a member from the list of people currently working on a challenge.

    Args:
        challenge_thread: The thread associated to the CTF challenge.
        challenge: The challenge document.
        member: The member to be removed.
    """
    challenge["players"].remove(member.name)
    _challenge_repo.set_players(challenge["_id"], challenge["players"])
    await challenge_thread.remove_user(member)


async def update_credentials(
    interaction: discord.Interaction, credentials: dict
) -> None:
    """Save CTF credentials in the database and update the credentials channel.

    Args:
        interaction: The Discord interaction.
        credentials: The credentials dictionary.
    """
    ctf = _ctf_repo.find_by_guild_category(interaction.channel.category_id)
    _ctf_repo.update_credentials(ctf["_id"], credentials)

    creds_channel = discord.utils.get(
        interaction.guild.text_channels, id=ctf["guild_channels"]["credentials"]
    )
    await creds_channel.purge()
    await creds_channel.send(credentials["_message"], suppress_embeds=True)
