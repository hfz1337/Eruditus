"""HTML parsing utilities."""

from typing import TYPE_CHECKING, Optional

from bs4 import BeautifulSoup
from utils.formatting import extract_filename_from_url

if TYPE_CHECKING:
    from platforms.base import ChallengeFile


def convert_attachment_url(url: str, base_url: Optional[str]) -> str:
    """Convert attachment URL to an absolute URL.

    Args:
        url: The attachment url.
        base_url: Domain base url.

    Returns:
        Absolute url.
    """
    if not url.startswith("http") and base_url:
        url = f'{base_url.rstrip("/")}/{url.lstrip("/")}'

    return url


def parse_attachment(url: str, base_url: Optional[str]) -> "ChallengeFile":
    """Convert attachment URL to a ChallengeFile item.

    Args:
        url: The attachment url.
        base_url: Domain base url.

    Returns:
        Converted file.
    """
    # Import here to avoid circular imports
    from platforms.base import ChallengeFile

    return ChallengeFile(
        url=convert_attachment_url(url, base_url),
        name=extract_filename_from_url(url),
    )


def extract_images_from_html(
    description: Optional[str], base_url: Optional[str] = None
) -> Optional[list["ChallengeFile"]]:
    """Extract `img` tags from the HTML description.

    Args:
        description: The HTML content.
        base_url: Domain base url.

    Returns:
        Converted files.
    """
    if not description:
        return None

    result = []

    for img in BeautifulSoup(description, "html.parser").find_all("img"):
        src: Optional[str] = img.get("src")
        if not src:
            continue

        result.append(parse_attachment(src, base_url))

    return result
