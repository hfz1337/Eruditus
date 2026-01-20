from datetime import datetime
from typing import Any, Optional, Union

from platforms.base import Challenge, ChallengeSolver, Team
from pydantic import BaseModel, field_validator
from utils.formatting import html_to_markdown
from utils.html import extract_images_from_html, parse_attachment


class MessageResponse(BaseModel):
    message: str


class BaseValidResponse(BaseModel):
    success: bool

    @classmethod
    @field_validator("success")
    def success_must_be_true(cls, value: bool) -> bool:
        if value:
            return value
        raise ValueError("Success must be True")


class SolvesResponse(BaseValidResponse):
    """Response schema returned by `/api/v1/challenges/:id/solves`."""

    class Solver(BaseModel):
        account_id: int
        name: str
        date: str
        account_url: str

        def convert(self) -> ChallengeSolver:
            return ChallengeSolver(
                team=Team(id=str(self.account_id), name=self.name),
                solved_at=datetime.fromisoformat(self.date.rstrip("Z")),
            )

    data: list[Solver]


class CTFDChallenge(BaseModel):
    """CTFd challenge representation that could be returned from `/challenges/*`."""

    class Hint(BaseModel):
        id: int
        cost: int
        content: Optional[str] = None

    # Required fields
    id: int
    type: str
    name: str
    value: int
    solves: Optional[int] = None
    solved_by_me: bool
    category: str
    tags: list[dict[str, str] | str]

    # Optional fields
    is_first_solver: Optional[bool] = None
    template: Optional[str] = None
    script: Optional[str] = None
    initial: Optional[int] = None
    decay: Optional[int] = None
    minimum: Optional[int] = None
    description: Optional[str] = None
    connection_info: Optional[str] = None
    state: Optional[str] = None
    max_attempts: Optional[int] = None
    typedata: Optional[dict] = None
    attempts: Optional[int] = None
    files: Optional[list[str]] = None
    hints: Optional[list[Hint]] = None
    view: Optional[str] = None

    def convert(self, url_stripped: str) -> Challenge:
        return Challenge(
            id=str(self.id),
            tags=(
                [x["value"] if isinstance(x, dict) else str(x) for x in self.tags]
                if self.tags is not None
                else None
            ),
            category=self.category,
            name=self.name,
            description=html_to_markdown(self.description),
            value=self.value,
            files=(
                [parse_attachment(x, url_stripped) for x in self.files]
                if self.files is not None
                else None
            ),
            images=extract_images_from_html(self.description, url_stripped),
            connection_info=self.connection_info,
            solves=self.solves,
            solved_by_me=self.solved_by_me,
        )


class CTFDTeam(BaseModel):
    class Member(BaseModel):
        id: int
        oauth_id: Optional[Union[str, int]] = None
        name: str
        score: int

    pos: int
    account_id: int
    account_url: str
    account_type: str
    oauth_id: Optional[Union[str, int]] = None
    name: str
    score: int
    members: list[Member]

    def convert(self) -> Team:
        return Team(id=str(self.account_id), name=self.name, score=self.score)


class CTFDStanding(BaseModel):
    class Solve(BaseModel):
        challenge_id: Union[int, None]
        account_id: int
        team_id: int
        user_id: int
        value: int
        date: str

    id: int
    name: str
    solves: list[Solve]


class ChallengeResponse(BaseValidResponse):
    """Response schema returned by `/api/v1/challenges/:id`."""

    data: CTFDChallenge


class ChallengesResponse(BaseValidResponse):
    """Response schema returned by `/api/v1/challenges`."""

    data: list[CTFDChallenge]


class ScoreboardResponse(BaseValidResponse):
    """Response schema returned by `/api/v1/scoreboard`."""

    data: list[CTFDTeam]


class SubmissionResponse(BaseValidResponse):
    """Response schema returned by `/api/v1/challenges/attempt`."""

    class Data(BaseModel):
        status: str
        message: str

    data: Data


class UserResponse(BaseValidResponse):
    """Response schema returned by `/api/v1/teams/me`."""

    class Data(BaseModel):
        website: Optional[str] = None
        id: int
        members: list[int]
        oauth_id: Optional[Union[str, int]] = None
        email: Optional[str] = None
        country: Optional[str] = None
        captain_id: int
        fields: list[dict]
        affiliation: Optional[str] = None
        bracket: Optional[Any] = None
        name: str
        place: Optional[str] = None
        score: int

        def convert(self) -> Team:
            return Team(
                id=str(self.id),
                name=self.name,
                score=self.score,
            )

    data: Data


class StandingsResponse(BaseValidResponse):
    """Response schema returned by `/api/v1/scoreboard/top/10`."""

    data: dict[str, CTFDStanding]
