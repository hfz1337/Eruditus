from dataclasses import dataclass
from typing import Optional


@dataclass
class CTFTimeParticipatedEvent:
    """A CTFTime event participation information representation.

    Author:
        @es3n1n
    """

    place: int
    event_name: str

    ctf_points: float
    rating_points: Optional[float]


@dataclass
class CTFTimeTeam:
    """A CTFTime scraped team information representation.

    Author:
        @es3n1n
    """

    overall_points: float

    overall_rating_place: int
    country_place: Optional[int]

    participated_in: list[CTFTimeParticipatedEvent]
