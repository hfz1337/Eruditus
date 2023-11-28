from dataclasses import dataclass
from enum import IntEnum, auto, unique
from typing import Any, Optional


@unique
class CTFTimeDiffType(IntEnum):
    OVERALL_POINTS_UPDATE = auto()
    OVERALL_PLACE_UPDATE = auto()
    COUNTRY_PLACE_UPDATE = auto()
    EVENT_UPDATE = auto()


@dataclass
class CTFTimeParticipatedEvent:
    """A class representing information about participation in a CTFtime event.

    Author:
        @es3n1n
    """

    place: int
    event_id: int
    event_name: str
    ctf_points: float
    rating_points: Optional[float]


@dataclass
class CTFTimeTeam:
    """A class representing information about a team scraped from CTFtime.

    Author:
        @es3n1n
    """

    overall_points: float
    overall_rating_place: int
    country_place: Optional[int]
    country_code: Optional[str]
    participated_in: dict[int, CTFTimeParticipatedEvent]

    def __sub__(self, other) -> dict[CTFTimeDiffType, Any]:
        diff = {CTFTimeDiffType.EVENT_UPDATE: []}
        if not isinstance(other, CTFTimeTeam):
            raise TypeError(
                f"Cannot diff {self.__class__.__name__} and {other.__class__.__name__}"
            )

        if self.overall_points != other.overall_points:
            diff[CTFTimeDiffType.OVERALL_POINTS_UPDATE] = (
                self.overall_points,
                other.overall_points,
            )

        if self.overall_rating_place != other.overall_rating_place:
            diff[CTFTimeDiffType.OVERALL_PLACE_UPDATE] = (
                self.overall_rating_place,
                other.overall_rating_place,
            )

        if self.country_place != other.country_place:
            diff[CTFTimeDiffType.COUNTRY_PLACE_UPDATE] = (
                self.country_place,
                other.country_place,
            )

        for prev_event in self.participated_in.values():
            if not (curr_event := other.participated_in.get(prev_event.event_id)):
                continue

            if (
                prev_event.place != curr_event.place
                or prev_event.ctf_points != curr_event.ctf_points
                or prev_event.rating_points != curr_event.rating_points
            ):
                diff[CTFTimeDiffType.EVENT_UPDATE].append((prev_event, curr_event))

        return diff


@dataclass
class LeaderboardEntry:
    """A class representing a row from the CTFtime leaderboard."""

    position: int
    country_position: Optional[int]
    team_id: int
    team_name: str
    country_code: Optional[str]
    points: float
    events: int
