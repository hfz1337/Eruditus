from dataclasses import dataclass
from enum import IntEnum, auto, unique
from sys import float_info
from typing import Optional, TypeAlias, Union

from lib.ctftime.types import CTFTimeParticipatedEvent, CTFTimeTeam

DiffItemType: TypeAlias = Union[CTFTimeTeam, CTFTimeParticipatedEvent]


@dataclass
class CTFTimeTeamDiff:
    """A CTFTime team difference representation.

    Author:
        @es3n1n
    """

    @unique
    class Type(IntEnum):
        # Rankings (DiffItemType = CTFTimeTeam)
        RANKING_OVERALL_POINTS_CHANGE = auto()
        RANKING_OVERALL_PLACE_CHANGE = auto()
        RANKING_COUNTRY_PLACE_CHANGE = auto()

        # Events (DiffItemType = CTFTimeParticipatedEvent)
        EVENT_ADDED = auto()
        EVENT_REMOVED = auto()
        EVENT_PLACE_CHANGE = auto()
        EVENT_CTF_PTS_CHANGE = auto()
        EVENT_RATING_PTS_CHANGE = auto()

    type: Type

    previous: Optional[DiffItemType]
    current: Optional[DiffItemType]


def diff_ctftime_team(
    previous: CTFTimeTeam, current: CTFTimeTeam
) -> list[CTFTimeTeamDiff]:
    """Diff two CTFTime teams.

    Args:
        previous: Previously stored CTFTime team info.
        current: Current CTFTime team info.

    Returns:
        A list of changes.
    """
    result = list()

    def push_change(
        change_type: CTFTimeTeamDiff.Type,
        prev: Optional[DiffItemType] = previous,
        cur: Optional[DiffItemType] = current,
    ) -> None:
        result.append(CTFTimeTeamDiff(type=change_type, previous=prev, current=cur))

    # Ranking changes
    if previous.overall_points != current.overall_points:
        push_change(CTFTimeTeamDiff.Type.RANKING_OVERALL_POINTS_CHANGE)
    if previous.overall_rating_place != current.overall_rating_place:
        push_change(CTFTimeTeamDiff.Type.RANKING_OVERALL_PLACE_CHANGE)
    if previous.country_place != current.country_place:
        push_change(CTFTimeTeamDiff.Type.RANKING_COUNTRY_PLACE_CHANGE)

    # Build O(1) map to access all events by their IDs
    previous_events: dict[int, CTFTimeParticipatedEvent] = {
        event.event_id: event for event in previous.participated_in
    }
    current_events: dict[int, CTFTimeParticipatedEvent] = {
        event.event_id: event for event in current.participated_in
    }

    # Looking for newly added events
    for current_event in current_events.values():
        if current_event.event_id in previous_events:
            continue

        push_change(CTFTimeTeamDiff.Type.EVENT_ADDED, None, current_event)

    # Looking for the event changes
    for previous_event in previous_events.values():
        # Try to get the current info of this event
        current_event = current_events.get(previous_event.event_id, None)

        def push_event_change(change_type: CTFTimeTeamDiff.Type) -> None:
            return push_change(change_type, previous_event, current_event)

        # If event was removed
        if not current_event:
            push_event_change(CTFTimeTeamDiff.Type.EVENT_REMOVED)
            continue

        # Place change
        if current_event.place != previous_event.place:
            push_event_change(CTFTimeTeamDiff.Type.EVENT_PLACE_CHANGE)
            continue

        # CTF pts change
        if (
            abs(current_event.ctf_points - previous_event.ctf_points)
            >= float_info.epsilon
        ):
            push_event_change(CTFTimeTeamDiff.Type.EVENT_CTF_PTS_CHANGE)
            continue

        # Rating pts change
        if (
            (not current_event.rating_points or not previous_event.rating_points)
            and (current_event.rating_points or previous_event.rating_points)
        ) or (
            abs(
                (current_event.rating_points or 0.0)
                - (previous_event.rating_points or 0.0)
            )
            >= float_info.epsilon
        ):
            push_event_change(CTFTimeTeamDiff.Type.EVENT_RATING_PTS_CHANGE)
            continue

    # We are done here
    return result
