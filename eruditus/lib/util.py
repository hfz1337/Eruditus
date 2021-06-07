from string import ascii_lowercase, digits
from hashlib import md5

import logging
from logging import RootLogger

from pymongo import MongoClient

import discord
from discord import Guild

from config import (
    DBNAME_PREFIX,
    CONFIG_COLLECTION,
    MINIMUM_PLAYER_COUNT,
    VOTING_STARTS_COUNTDOWN,
    VOTING_VERDICT_COUNTDOWN,
)


def truncate(text: str, maxlen=1024) -> str:
    """Truncate a paragraph to a specific length.

    Args:
        text: The paragraph to truncate.
        maxlen: The maximum length of the paragraph.

    Returns:
        The truncated paragraph.
    """
    etc = "[…]"
    return f"{text[:maxlen - len(etc)]}{etc}" if len(text) > maxlen - len(etc) else text


def sanitize_channel_name(name: str) -> str:
    """Filter out characters that aren't allowed by Discord for guild channels.

    Args:
        name: Channel name.

    Returns:
        Sanitized channel name.
    """
    whitelist = ascii_lowercase + digits + "-_"
    name = name.lower().replace(" ", "-")

    for char in name:
        if char not in whitelist:
            name = name.replace(char, "")

    while "--" in name:
        name = name.replace("--", "-")

    return name


def derive_colour(role_name: str) -> int:
    """Derive a colour for the CTF role by taking its MD5 hash and using the first 3
    bytes as the colour.

    Args:
        role_name: Name of the role we wish to set a colour for.

    Returns:
        An integer representing an RGB colour.
    """
    return int(md5(role_name.encode()).hexdigest()[:6], 16)


async def setup_database(mongo: MongoClient, guild: Guild) -> None:
    """Set up a database for a guild.

    Args:
        mongo: MongoDB client handle
        guild: The guild to set up the database for.
    """
    # Create an announcements channel
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(
            send_messages=False, add_reactions=False
        )
    }
    announcement_channel = await guild.create_text_channel(
        name="📢 Event Announcements",
        overwrites=overwrites,
    )

    # Create CTF archive category channel
    overwrites = {guild.default_role: discord.PermissionOverwrite(send_messages=False)}
    archive_category_channel = await guild.create_category(
        name="📁 CTF Archive",
        overwrites=overwrites,
    )

    # Insert the config document into the config collection of that guild's own db
    mongo[f"{DBNAME_PREFIX}-{guild.id}"][CONFIG_COLLECTION].insert_one(
        {
            "voting_verdict_countdown": VOTING_VERDICT_COUNTDOWN,
            "voting_starts_countdown": VOTING_STARTS_COUNTDOWN,
            "minimum_player_count": MINIMUM_PLAYER_COUNT,
            "archive_category_channel": archive_category_channel.id,
            "announcement_channel": announcement_channel.id,
        }
    )


def setup_logger(level: int) -> RootLogger:
    """Set up logging.

    Args:
        level: Logging level.

    Returns:
        The logger.
    """
    log_formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)-8s:%(name)-24s] => %(message)s"
    )

    logger = logging.getLogger()
    logger.setLevel(level)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(log_formatter)

    logger.addHandler(stream_handler)

    return logger
