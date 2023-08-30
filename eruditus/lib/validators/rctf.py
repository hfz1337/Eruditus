from typing import Optional

from pydantic import BaseModel, field_validator


class BaseValidResponse(BaseModel):
    kind: str

    @field_validator("kind")
    @classmethod
    def kind_validator(cls, value: str) -> str:
        if value.startswith("good") or value.startswith("bad"):
            return value
        raise ValueError("Unknown kind or Internal Server error")


class LeaderboardResponse(BaseValidResponse):
    """Reponse schema returned by `/api/v1/leaderboard/now`."""

    class Data(BaseModel):
        class Team(BaseModel):
            id: str
            name: str
            score: int

        total: int
        leaderboard: list[Team]

    message: str
    data: Data


class UserResponse(BaseValidResponse):
    """Reponse schema returned by `/api/v1/users/me`."""

    class Data(BaseModel):
        class Challenge(BaseModel):
            category: str
            name: str
            points: int
            solves: int
            id: str
            createdAt: int

        name: str
        ctftimeId: Optional[int] = None
        division: str
        score: int
        globalPlace: int
        divisionPlace: int
        solves: list[Challenge]
        teamToken: str
        allowedDivisions: list[str]
        id: str
        email: str

    message: str
    data: Data


class ChallengesReponse(BaseValidResponse):
    """Reponse schema returned by `/api/v1/challs`."""

    class Data(BaseModel):
        class File(BaseModel):
            url: str
            name: str

        files: list[File]
        description: str
        author: str
        points: int
        id: str
        name: str
        category: str
        solves: int

    message: str
    data: Data


class AuthResponse(BaseValidResponse):
    """Reponse schema returned by `/api/v1/auth/register` and `/api/v1/auth/login`."""

    class Data(BaseModel):
        authToken: str

    message: str
    data: Data


class SolvesResponse(BaseValidResponse):
    """Reponse schema returned by `/api/v1/challs/:id/solves`."""

    class Data(BaseModel):
        class Solve(BaseModel):
            id: str
            createdAt: str
            userId: str
            userName: str

        solves: list[Solve]

    message: str
    data: Data


class SubmissionResponse(BaseValidResponse):
    """Reponse schema returned by `/api/v1/challs/:id/submit`."""

    message: str
    data: None
