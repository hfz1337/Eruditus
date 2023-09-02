import re
from datetime import datetime
from typing import Any, Optional

from bs4 import BeautifulSoup
from markdownify import markdownify as html2md
from pydantic import BaseModel, field_validator

from lib.platforms.abc import Challenge, ChallengeFile, ChallengeSolver, Team
from lib.util import extract_filename_from_url


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
    solves: int
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

    def _description_to_markdown(self) -> None:
        if self.description is None:
            return None

        # Convert to markdown.
        md = html2md(
            self.description,
            heading_style="atx",
            escape_asterisks=False,
            escape_underscores=False,
        )
        # Remove all images.
        md = re.sub(r'[^\S\r\n]*!\[[^\]]*\]\((.*?)\s*("(?:.*[^"])")?\s*\)\s*', "", md)
        # Remove multilines.
        md = re.sub(r"\n+", "\n", md)
        return md

    def convert(self, url_stripped: str) -> Challenge:
        return Challenge(
            id=str(self.id),
            tags=[x["value"] if isinstance(x, dict) else str(x) for x in self.tags]
            if self.tags is not None
            else None,
            category=self.category,
            name=self.name,
            description=self._description_to_markdown(),
            value=self.value,
            files=[
                ChallengeFile(
                    url=f"{url_stripped}/{x}", name=extract_filename_from_url(x)
                )
                for x in self.files
            ]
            if self.files is not None
            else None,
            images=[
                ChallengeFile(
                    url=f"{url_stripped}/{img['src'].lstrip('/')}"
                    if img["src"].startswith("/")
                    else img["src"],
                    name=extract_filename_from_url(img["src"]),
                )
                for img in BeautifulSoup(self.description, "html.parser").findAll("img")
                if img.get("src")
            ]
            if self.description is not None
            else None,
            connection_info=self.connection_info,
            solves=self.solves,
        )


class CTFDTeam(BaseModel):
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

    def convert(self) -> Team:
        return Team(id=str(self.account_id), name=self.name, score=self.score)


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
        website: Optional[str]
        id: int
        members: list[int]
        oauth_id: Optional[str]
        email: Optional[str]
        country: Optional[str]
        captain_id: int
        fields: list[dict]
        affiliation: Optional[str]
        bracket: Optional[Any]
        name: str
        place: Optional[str]
        score: int

        def convert(self) -> Team:
            return Team(
                id=str(self.id),
                name=self.name,
                score=self.score,
            )

    data: Data
