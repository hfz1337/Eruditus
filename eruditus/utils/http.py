"""HTTP and URL utilities."""

import json
import logging
import urllib.parse
from typing import Any, Optional, Type, TypeVar

from aiohttp import ClientResponse
from pydantic import TypeAdapter, ValidationError
from utils.validation import in_range

T = TypeVar("T")
_log = logging.getLogger(__name__)


def strip_url_components(url: str) -> str:
    """Strip the path, query parameters and fragments from a URL.

    Args:
        url: The URL to parse.

    Returns:
        The base URL.
    """
    parsed_url = urllib.parse.urlparse(url)
    return f"{parsed_url.scheme}://{parsed_url.netloc}"


def extract_rctf_team_token(invite_url: str) -> Optional[str]:
    """Extract the rCTF team token from an invitation URL.

    Args:
        invite_url: The rCTF invite URL
            (e.g., https://rctf.example.com/login?token=<token>).

    Returns:
        The team token.
    """
    parsed_url = urllib.parse.urlparse(invite_url)
    params = urllib.parse.parse_qs(parsed_url.query)
    if not (team_token := params.get("token")):
        return None

    return team_token[0]


async def deserialize_response(
    response: ClientResponse, model: Type[T], suppress_warnings: bool = False
) -> Optional[T]:
    """Validate response status code and JSON content.

    Args:
        response: The HTTP response.
        model: The pydantic model used to validate the JSON response.
        suppress_warnings: No warnings would be printed if set to true.

    Returns:
        A deserialized response if the response is valid, None otherwise.
    """
    response_ranges: list[list[int]] = [
        [200, 299],  # ok
        [400, 499],  # client-side errors
    ]

    valid_status_code: bool = False
    for response_range in response_ranges:
        valid_status_code |= in_range(response.status, *response_range)

    if not valid_status_code:
        return None

    response_json: dict[str, Any] = await response.json()

    try:
        return TypeAdapter(model).validate_python(response_json)
    except ValidationError as e:
        if not suppress_warnings:
            _log.warning(
                "Could not validate response data using the %s model:\n%s\nErrors - %s",
                model.__name__,
                json.dumps(response_json, indent=2),
                str(e),
            )
        return None
