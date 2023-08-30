from typing import Optional

from pydantic import BaseModel, field_validator


class BaseValidResponse(BaseModel):
    success: bool

    @field_validator("success")
    @classmethod
    def success_must_be_true(cls, value: bool) -> bool:
        if value:
            return value
        raise ValueError("Success must be True")


class SolvesResponse(BaseValidResponse):
    """Reponse schema returned by `/api/v1/challenges/:id/solves`."""

    class Solver(BaseModel):
        account_id: int
        name: str
        date: str
        account_url: str

    data: list[Solver]


class ChallengeResponse(BaseValidResponse):
    """Reponse schema returned by `/api/v1/challenges/:id`."""

    class Challenge(BaseModel):
        id: int
        name: str
        value: int
        initial: Optional[int] = None
        decay: Optional[int] = None
        minimum: Optional[int] = None
        description: str
        connection_info: Optional[str] = None
        category: str
        state: str
        max_attempts: int
        type: str
        typedata: dict = None
        solves: int
        solved_by_me: bool
        is_first_solver: bool
        attempts: int
        files: list[str] = None
        tags: list[str]
        hints: list[str]
        view: str

    data: Challenge


class ChallengesResponse(BaseValidResponse):
    """Reponse schema returned by `/api/v1/challenges`."""

    class Challenge(BaseModel):
        id: int
        type: str
        name: str
        value: int
        solves: int
        solved_by_me: bool
        is_first_solver: bool
        category: str
        tags: list[dict[str, str]]
        template: str
        script: str

    data: list[Challenge]


class ScoreboardResponse(BaseValidResponse):
    """Reponse schema returned by `/api/v1/scoreboard`."""

    class Team(BaseModel):
        class Member(BaseModel):
            id: int
            oauth_id: Optional[str] = None
            name: str
            score: int

        pos: int
        account_id: int
        account_url: str
        account_type: str
        oauth_id: Optional[str] = None
        name: str
        score: int
        members: list[Member]

    data: list[Team]


class SubmissionResponse(BaseValidResponse):
    """Reponse schema returned by `/api/v1/challenges/attempt`."""

    class Data(BaseModel):
        status: str
        message: str

    data: Data
