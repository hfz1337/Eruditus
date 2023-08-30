import logging
from datetime import datetime, timezone
from hashlib import md5
from logging import Logger
from string import ascii_lowercase, digits
from typing import Any, Dict, List, Optional, Type, TypeVar

from aiohttp import ClientResponse
from pydantic import TypeAdapter, ValidationError

T = TypeVar("T")


def get_local_time() -> datetime:
    """Return offset aware local time.

    Returns:
        Offset aware datetime object.
    """
    local_timezone = datetime.now(timezone.utc).astimezone().tzinfo
    return datetime.now(local_timezone)


def truncate(text: str, max_len: int = 1024) -> str:
    """Truncate a paragraph to a specific length.

    Args:
        text: The paragraph to truncate.
        max_len: The maximum length of the paragraph.

    Returns:
        The truncated paragraph.
    """
    etc = "\n[…]"
    return (
        f"{text[:max_len - len(etc)]}{etc}" if len(text) > max_len - len(etc) else text
    )


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


def setup_logger(level: int) -> Logger:
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


def in_range(value: int, minimal: int, maximum: int) -> bool:
    """Check whether number is in desired range.

    Args:
        value: The value that is going to be checked.
        minimal: Min value.
        maximum: Max value.

    Returns:
        True or false.
    """
    return minimal <= value <= maximum


def is_empty_string(value: Optional[str]) -> bool:
    """Check whether a string is empty.

    Args:
        value: The string that is going to be checked.

    Returns:
        True if the string is empty or None, False otherwise.

    Raises:
        TypeError: if `value` is of type other than `None` or `str`.
    """
    if value is not None and not isinstance(value, str):
        raise TypeError("Value must be either None or a string")
    return value is None or value.strip() == ""


async def deserialize_response(response: ClientResponse, model: Type[T]) -> Optional[T]:
    """Validate response status code and JSON content.

    Args:
        response: The HTTP response.
        model: The pydantic model used to validate the JSON response.

    Returns:
        A deserialized response if the response is valid, None otherwise.
    """
    response_ranges: List[List[int]] = [
        [200, 299],  # ok
        [400, 499],  # client-side errors
    ]

    valid_status_code: bool = False
    for response_range in response_ranges:
        valid_status_code |= in_range(response.status, *response_range)

    if not valid_status_code:
        return None

    response_json: Dict[str, Any] = await response.json()

    try:
        return TypeAdapter(model).validate_python(response_json)
    except ValidationError:
        return None
