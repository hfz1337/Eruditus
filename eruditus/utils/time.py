"""Time and timezone utilities."""

from datetime import datetime, timezone


def get_local_time() -> datetime:
    """Return offset aware local time.

    Returns:
        Offset aware datetime object.
    """
    local_timezone = datetime.now(timezone.utc).astimezone().tzinfo
    return datetime.now(local_timezone)
