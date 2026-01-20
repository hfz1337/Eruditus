"""Discord event handlers for Eruditus."""

from events.scheduled_events import (
    handle_scheduled_event_end,
    handle_scheduled_event_start,
)

__all__ = [
    "handle_scheduled_event_start",
    "handle_scheduled_event_end",
]
