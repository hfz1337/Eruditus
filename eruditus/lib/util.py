from datetime import datetime, timezone

from string import ascii_lowercase, digits
from hashlib import md5

import logging
from logging import RootLogger


def get_local_time() -> datetime:
    """Return offset aware local time.

    Returns:
        Offset aware datetime object.
    """
    local_timzone = datetime.now(timezone.utc).astimezone().tzinfo
    return datetime.now(local_timzone)


def truncate(text: str, maxlen: int = 1024) -> str:
    """Truncate a paragraph to a specific length.

    Args:
        text: The paragraph to truncate.
        maxlen: The maximum length of the paragraph.

    Returns:
        The truncated paragraph.
    """
    etc = "\n[…]"
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
