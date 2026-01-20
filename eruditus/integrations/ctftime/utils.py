from datetime import datetime, timezone


def ctftime_date_to_datetime(ctftime_date: str) -> datetime:
    """Convert CTFtime date to an offset-aware datetime object.

    Args:
        ctftime_date: Date retrieved from the CTFtime event.

    Returns:
        Offset-aware datetime object.
    """
    return datetime.strptime(
        ctftime_date.replace("Sept", "Sep"),
        f"%a, %d {'%b.' if '.' in ctftime_date else '%B'} %Y, %H:%M UTC",
    ).replace(tzinfo=timezone.utc)
