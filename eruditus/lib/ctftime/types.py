from dataclasses import dataclass
from typing import Optional


@dataclass
class CTFTimeParticipatedEvent:
    """A CTFTime event participation information representation.

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
    """A CTFTime scraped team information representation.

    Author:
        @es3n1n
    """

    overall_points: float

    overall_rating_place: int
    country_place: Optional[int]

    participated_in: list[CTFTimeParticipatedEvent]

    def find_event_by_id(self, event_id: int) -> Optional[CTFTimeParticipatedEvent]:
        """Attempt to find the participated event by using its ID.

        Args:
            event_id: The event ID.

        Returns:
             Nullable event info.
        """
        for event in self.participated_in:
            if event.event_id != event_id:
                continue

            return event

        return None
