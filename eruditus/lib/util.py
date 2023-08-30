import logging
from datetime import datetime, timezone
from hashlib import md5
from logging import RootLogger
from string import ascii_lowercase, digits
from typing import Any, Dict

from aiohttp import ClientResponse
from pydantic import BaseModel, ValidationError


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


async def validate_response(response: ClientResponse, validator: BaseModel) -> bool:
    """Validate response status code and JSON content.

    Args:
        response: The HTTP response.
        validator: The pydantic validator used to validate the JSON response.

    Returns:
        True if the response is valid, False otherwise.
    """
    if response.status != 200:
        return False

    response_json: Dict[str, Any] = await response.json()
    try:
        _ = validator(**response_json)
        return True
    except ValidationError:
        return False
