from datetime import datetime, timezone

from string import ascii_lowercase, digits
from hashlib import md5

import logging
from logging import RootLogger
from typing import Dict, Any

from aiohttp import ClientResponse


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


# @note: @es3n1n: Check the content w/o the status checks
async def validate_response_json(
    response: ClientResponse, *validate_fields: str, **validate_kw: Any
) -> bool:
    """
    @note: @es3n1n: I am too lazy to write typehints for the `validate_kw`,
    you can pass it like this:
        * validate_response(
            response,
            'something',
            data=['a', 'b'],
            data={'a': ['b'], 'b': {'c': ['s']}}
        )
        * validate_response(
            response,
            data={'response': {'success': True}}
        )
    """
    # If there's nothing to validate
    if len(validate_fields) == 0 and len(validate_kw) == 0:
        return True

    # Validating json fields
    response_json: Dict[str, Any] = await response.json()

    # Validators impl
    # @todo: @es3n1n: this could be implemented way better than this
    def validate_field(data, values):
        # Validating json keys
        if isinstance(values, list):
            for field in values:
                if field not in data:
                    return False
            return True

        # Validating json trees
        if isinstance(values, dict):
            for field, value in values.items():
                if field not in data:
                    return False

                if not validate_field(data[field], value):
                    return False

            return True

        # Exact matching
        return data == values

    # Validating args
    if len(validate_fields) > 0:
        for field in validate_fields:
            if field not in response_json:
                return False

        return True

    # Validate kwargs
    for key, value in validate_kw.items():
        if key not in response_json:
            return False

        if not validate_field(response_json[key], value):
            return False

    # Yay
    return True


async def validate_response(
    response: ClientResponse, *validate_fields: str, **validate_kw: Any
) -> bool:
    # Validating response code
    if response.status != 200:
        return False

    # Validating content
    return await validate_response_json(response, *validate_fields, **validate_kw)
