"""Text formatting utilities."""

import os
import re
import urllib.parse
from string import ascii_lowercase, digits
from typing import Optional

from markdownify import markdownify as html2md


def truncate(text: str, max_len: int = 1024) -> str:
    """Truncate a paragraph to a specific length.

    Args:
        text: The paragraph to truncate.
        max_len: The maximum length of the paragraph.

    Returns:
        The truncated paragraph.
    """
    etc = "\n[...]"
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


def html_to_markdown(description: Optional[str]) -> Optional[str]:
    """Convert HTML content to Markdown.

    Args:
        description: The HTML content.

    Returns:
        Converted result.
    """
    if description is None:
        return None

    # Convert to markdown.
    md = html2md(
        description,
        heading_style="atx",
        escape_asterisks=False,
        escape_underscores=False,
    )

    # Remove all images.
    md = re.sub(r'[^\S\r\n]*!\[[^\]]*\]\((.*?)\s*("(?:.*[^"])")?\s*\)\s*', "", md)

    # Remove multilines.
    md = re.sub(r"\n+", "\n", md)

    return md


def extract_filename_from_url(url: str) -> str:
    """Extract a filename from a URL.

    Args:
        url: The URL to extract the filename from.

    Returns:
        The filename.
    """
    return os.path.basename(urllib.parse.urlparse(url).path)
