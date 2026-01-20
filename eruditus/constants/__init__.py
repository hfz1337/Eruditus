"""Constants used throughout the application."""

from constants.channels import CategoryPrefixes, ChannelNames, ThreadPrefixes
from constants.colors import EmbedColours
from constants.emojis import Emojis
from constants.errors import ErrorMessages
from constants.limits import (
    DEFAULT_AUTO_ARCHIVE_DURATION,
    MAX_AUTOCOMPLETE_CHOICES,
    MAX_EMBED_FIELDS,
)

__all__ = [
    # Emojis
    "Emojis",
    # Channels
    "ChannelNames",
    "ThreadPrefixes",
    "CategoryPrefixes",
    # Colors
    "EmbedColours",
    # Errors
    "ErrorMessages",
    # Limits
    "MAX_AUTOCOMPLETE_CHOICES",
    "MAX_EMBED_FIELDS",
    "DEFAULT_AUTO_ARCHIVE_DURATION",
]
