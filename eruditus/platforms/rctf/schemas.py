from datetime import datetime
from typing import Any, Optional

from platforms.base import Challenge, ChallengeFile, ChallengeSolver, Team
from pydantic import BaseModel, field_validator
from utils.formatting import html_to_markdown
from utils.html import convert_attachment_url, extract_images_from_html


class BaseRCTFResponse(BaseModel):
    kind: str

    def is_good(self) -> bool:
        return self.kind.startswith("good")

    def is_not_good(self) -> bool:
        return not self.is_good()

    def is_bad(self) -> bool:
        return self.kind.startswith("bad")

    @classmethod
    @field_validator("kind")
    def kind_validator(cls, value: str) -> str:
        if value.startswith("good") or value.startswith("bad"):
            return value
        raise ValueError("Unknown kind or Internal Server error")


class RCTFChallenge(BaseModel):
    """General rCTF challenge representation returned by `/challs`, `/me`, etc."""

    category: str
    name: str
    points: Optional[int]
    solves: Optional[int]
    id: str

    # Optional values that would be set only in `/challs` response
    class File(BaseModel):
        url: str
        name: str

        def convert(self, url_stripped: str) -> ChallengeFile:
            return ChallengeFile(
                url=convert_attachment_url(self.url, url_stripped), name=self.name
            )

    files: Optional[list[File]] = None
    description: Optional[str] = None
    author: Optional[str] = None

    def convert(self, url_stripped: str) -> Challenge:
        return Challenge(
            id=self.id,
            category=self.category,
            name=self.name,
            description=html_to_markdown(self.description),
            value=self.points if self.points is not None else 0,
            files=(
                [x.convert(url_stripped) for x in self.files]
                if self.files is not None
                else None
            ),
            images=extract_images_from_html(self.description, url_stripped),
            solves=self.solves if self.solves is not None else 0,
        )


class RCTFTeam(BaseModel):
    """General rCTF team representation returned by `/api/v1/leaderboard/now`, `/me`."""

    id: str
    name: str
    score: Optional[int] = None

    # Optional values that would be set only for our team, i.e., you won't get these
    # values from the leaderboard
    ctftimeId: Optional[int] = None
    division: Optional[str] = None
    globalPlace: Optional[int] = None
    divisionPlace: Optional[int] = None
    solves: Optional[list[RCTFChallenge]] = None
    teamToken: Optional[str] = None
    allowedDivisions: Optional[list[str]] = None
    email: Optional[str] = None

    def convert(self, url_stripped: str) -> Team:
        return Team(
            id=self.id,
            name=self.name,
            score=self.score,
            invite_token=self.teamToken,
            solves=(
                [x.convert(url_stripped) for x in self.solves]
                if self.solves is not None
                else None
            ),
        )


class RCTFStanding(BaseModel):
    class Solve(BaseModel):
        time: int
        score: int

    id: str
    name: str
    points: list[Solve]


class LeaderboardResponse(BaseRCTFResponse):
    """Response schema returned by `/api/v1/leaderboard/now`."""

    class Data(BaseModel):
        total: int
        leaderboard: list[RCTFTeam]

    message: str
    data: Optional[Data]


class UserResponse(BaseRCTFResponse):
    """Response schema returned by `/api/v1/users/me`."""

    message: str
    data: RCTFTeam


class ChallengesReponse(BaseRCTFResponse):
    """Response schema returned by `/api/v1/challs`."""

    message: str
    data: Optional[list[RCTFChallenge]]


class AuthResponse(BaseRCTFResponse):
    """Response schema returned by `/api/v1/auth/register` and `/api/v1/auth/login`."""

    class Data(BaseModel):
        authToken: Optional[str] = None

    message: str
    data: Optional[Data] = None


class SolvesResponse(BaseRCTFResponse):
    """Response schema returned by `/api/v1/challs/:id/solves`."""

    class Data(BaseModel):
        class Solve(BaseModel):
            id: str
            createdAt: int
            userId: str
            userName: str

            def convert(self) -> ChallengeSolver:
                return ChallengeSolver(
                    team=Team(id=self.userId, name=self.userName),
                    solved_at=datetime.fromtimestamp(self.createdAt / 100),
                )

        solves: list[Solve]

    message: str
    data: Data


class SubmissionResponse(BaseRCTFResponse):
    """Response schema returned by `/api/v1/challs/:id/submit`."""

    message: str
    data: Optional[dict[str, Any]] = None


class StandingsResponse(BaseRCTFResponse):
    """Response schema returned by `/api/v1/leaderboard/graph`."""

    class Data(BaseModel):
        graph: list[RCTFStanding]

    message: str
    data: Data
