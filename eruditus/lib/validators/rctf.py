from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator

from ..platforms.abc import Challenge, ChallengeFile, ChallengeSolver, Team


class BaseRCTFResponse(BaseModel):
    kind: str

    def is_good(self) -> bool:
        return self.kind.startswith("good")

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
    points: int
    solves: int
    id: str

    # Optional vales that would be set only in `/challs` response
    class File(BaseModel):
        url: str
        name: str

        def convert(self) -> ChallengeFile:
            return ChallengeFile(url=self.url, name=self.name)

    files: Optional[list[File]] = None
    description: Optional[str] = None
    author: Optional[str] = None

    def convert(self) -> Challenge:
        return Challenge(
            id=self.id,
            category=self.category,
            name=self.name,
            description=self.description,
            value=self.points,
            files=[x.convert() for x in self.files] if self.files is not None else None,
            solves=self.solves,
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

    def convert(self) -> Team:
        return Team(
            id=self.id,
            name=self.name,
            score=self.score,
            invite_token=self.teamToken,
            solves=[x.convert() for x in self.solves]
            if self.solves is not None
            else None,
        )


class LeaderboardResponse(BaseRCTFResponse):
    """Response schema returned by `/api/v1/leaderboard/now`."""

    class Data(BaseModel):
        total: int
        leaderboard: list[RCTFTeam]

    message: str
    data: Data


class UserResponse(BaseRCTFResponse):
    """Response schema returned by `/api/v1/users/me`."""

    message: str
    data: RCTFTeam


class ChallengesReponse(BaseRCTFResponse):
    """Response schema returned by `/api/v1/challs`."""

    message: str
    data: list[RCTFChallenge]


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
    data: None
