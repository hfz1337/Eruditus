from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum, auto, unique
from typing import Any, AsyncIterator, Awaitable, Callable, Dict, List, Optional

from pydantic import field_validator


@dataclass
class Session:
    """A session representation.

    Author:
        @es3n1n

    Attributes:
        token: The authorization token.
        cookies: The session cookies.

    Methods:
        validate: Check the validity of this session.
    """

    token: Optional[str] = None
    cookies: Dict[str, str] = field(default_factory=dict)

    def validate(self) -> bool:
        return len(self.cookies) > 0 or self.token is not None


@dataclass
class ChallengeSolver:
    """A class for representing a challenge solver.

    Author:
        @es3n1n

    Attributes:
        team: The team that solved a challenge.
        solved_at: The solve time.
    """

    team: "Team"
    solved_at: datetime


@dataclass
class ChallengeFile:
    """A class representing a challenge file attachment.

    Author:
        @es3n1n

    Attributes:
        url: The file attachment's URL.
        name: The file name.
    """

    url: str
    name: Optional[str] = None


@dataclass
class Challenge:
    """A class representing a CTF challenge.

    Author:
        @es3n1n

    Attributes:
        id: The challenge ID (could be either numerical or in another form such as a
            UUID).
        tags: The challenge tags.
        category: The challenge category.
        name: The challenge name.
        description: The challenge description.
        value: The challenge value (i.e., number of awarded points) at the time of
            its creation (this may change if the scoring is dynamic).
        files: A list of file attachments associated to this challenge.
        connection_info: The challenge connection info.
        solves: The number of solves on this challenge.
        solved_by: List of solvers who solved this challenge.

    TODO:
        Add max_attempts/attempts
        Add hints
        Add connection_info

    Notes:
        Some fields can remain unset depending on the platform.
        Not all platforms use a numerical ID for the challenges, for example, rCTF uses
        a UUID while CTFd prefers numerical identifiers. It is thus important to convert
        the ID to an integer before using it with CTFd for example.
    """

    id: str
    tags: Optional[List[str]] = None
    category: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    value: Optional[int] = None
    files: Optional[List[ChallengeFile]] = None
    connection_info: Optional[str] = None
    solves: Optional[int] = None
    solved_by: Optional[List[ChallengeSolver]] = None

    @classmethod
    @field_validator("solved_by", mode="before")
    def validate_solved_by(
        cls, value: Optional[List[ChallengeSolver]]
    ) -> Optional[List[ChallengeSolver]]:
        if value is None:
            return value

        # Sorting the solvers by their solve time
        value.sort(key=lambda x: x.solved_at)
        return value


@unique
class SubmittedFlagState(IntEnum):
    """An enum representing submitted flag states.

    Author:
        @es3n1n
    """

    ALREADY_SUBMITTED = auto()
    INCORRECT = auto()
    CORRECT = auto()
    CTF_NOT_STARTED = auto()
    CTF_PAUSED = auto()
    CTF_ENDED = auto()
    INVALID_CHALLENGE = auto()
    INVALID_USER = auto()
    RATE_LIMITED = auto()
    UNKNOWN = auto()


@dataclass
class Retries:
    """A class representing submission retries.

    Author:
        @es3n1n

    Attributes:
        left: The number of retries left.
        out_of: The maximum number of retries, or None if the number of retries is
        unlimited.
    """

    left: int
    out_of: Optional[int] = None


@dataclass
class SubmittedFlag:
    """A class representing a flag submission.

    Author:
        @es3n1n

    Attributes:
        state: The submitted flag state.
        retries: Submission retries.
        is_first_blood: Whether this was the first successful submission.
    """

    state: SubmittedFlagState
    retries: Optional[Retries] = None
    is_first_blood: bool = False

    async def update_first_blood(
        self,
        ctx: "PlatformCTX",
        solvers_getter: Callable[..., AsyncIterator[ChallengeSolver]],
        challenge_getter: Callable[..., Awaitable[Optional[Challenge]]],
        challenge_id: str,
        me: Optional["Team"] = None,
    ) -> None:
        """Update the `is_first_blood` attribute.

        Arguments:
            ctx: The platform context.
            solvers_getter: A platform-specific function for retrieving the solver for
                a specific challenge.
            challenge_getter: A platform-specific function for retrieving the challenge
                by its ID.
            challenge_id: The ID of the challenge for which we want to check if we got
                first blood.
            me: A representation of our team.
        """
        if self.state != SubmittedFlagState.CORRECT:
            return

        # If there's no team object, then we should try to detect first blood via
        # pulling solves count of the challenge
        if me is None:
            challenge: Optional[Challenge] = await challenge_getter(ctx, challenge_id)
            self.is_first_blood = challenge is not None and challenge.solves <= 1
            return

        # Querying solvers of this challenge.
        solvers_generator: Optional[AsyncIterator[ChallengeSolver]] = solvers_getter(
            ctx=ctx, challenge_id=challenge_id, limit=1
        )
        if solvers_generator is None:
            # Something went wrong.
            return

        first_solver: Optional[ChallengeSolver] = await anext(solvers_generator, None)
        if first_solver is None:
            # XXX (hfz) Something went wrong, unless there's caching at play and the
            # platform is still returning an empty list. It doesn't apply to CTFd or
            # rCTF, this might need a reimplementation if we encounter a platform with
            # such behavior, until then, keeping the code simple is preferred.
            # Note that this assumes the returned solvers are sorted by solve time.
            return

        self.is_first_blood = first_solver.team == me


@dataclass
class Team:
    """A class representing CTF team information as returned by the CTF platform.

    Author:
        @es3n1n

    Attributes:
        id: The team ID.
        name: The team name.
        score: The current team score.
        invite_token: The team invite token (only used for rCTF.)
        solves: A list of challenges that this team solved (only used for rCTF).
    """

    id: str
    name: str
    score: Optional[int] = None
    invite_token: Optional[str] = None
    solves: Optional[List[Challenge]] = None

    def __eq__(self, other: Optional["Team"]) -> bool:
        if other is None:
            return False

        return self.id == other.id or self.name == other.name


@dataclass
class RegistrationStatus:
    """A class representing a team registration status.

    Author:
        @es3n1n

    Attributes:
        success: Whether the registration was successful.
        message: The response message returned by the CTF platform.
        token: The authorization token returned by the CTF platform (only used for
            rCTF).
        invite: The team invite URL (only used for rCTF).
    """

    success: bool
    message: Optional[str] = None
    token: Optional[str] = None
    invite: Optional[str] = None


@dataclass
class PlatformCTX:
    """A class representing a platform context.

    Author:
        @es3n1n

    Attributes:
        base_url: The platform base URL.
        args: A custom set of arguments, such as `email`, `login`, `password`, `token`,
            and so on. None of these are required by default and everything should be
            checked within the platform itself.
        session: The session object for accessing private sections of a platform.

    Properties:
        url_stripped: Return the base URL without a trailing slash.

    Methods:
        get_args: Get arguments from the set of custom arguments, optionally extending
            them with additional items.
        validate_args: Validate an argument by checking its values against a set of
            invalid values.
        is_authorized: Check if our session is valid for querying private sections of
            the platform.
        login: Login to the CTF platform and store the login session.

    Notes:
        Ideally we should have automatic validation for the attributes (e.g., Pydantic).
    """

    base_url: str
    args: Dict[str, str] = field(default_factory=dict)
    session: Optional[Session] = None

    @property
    def url_stripped(self) -> str:
        return self.base_url.strip("/")

    @staticmethod
    def from_credentials(credentials: Dict[str, str]) -> "PlatformCTX":
        """Custom constructor that initializes a class instance from a set of
        credentials.

        Args:
            credentials: A dictionary of credentials. It must contain at least at the
            URL of the CTF platform.
        """
        return PlatformCTX(
            base_url=credentials["url"],
            args=credentials,
        )

    def get_args(self, *required_fields: str, **kwargs: str) -> Dict[str, str]:
        """Get arguments from the set of custom arguments (i.e., self.args), optionally
        extending them with additional items.

        Args:
            required_fields: A set of required field names.
            kwargs: Additional (key, value) pairs to include in the result.

        Returns:
            A dictionary of arguments (e.g., email, password, etc.).
        """
        result: Dict[str, str] = {
            key: value for key, value in self.args.items() if key in required_fields
        }

        for k, v in kwargs.items():
            result[k] = v

        return result

    def validate_arg(self, key: str, *invalid_values: Any) -> bool:
        """Validate an argument by checking its values against a set of invalid values.

        Args:
            key: The argument name.
            invalid_values: A set of invalid values to check against.

        Returns:
            True if the argument is valid, False otherwise.
        """
        if key not in self.args:
            return False

        return self.args not in invalid_values

    def is_authorized(self) -> bool:
        """Check whether our session is authorized.

        Returns:
            True if our session is authorized, False otherwise.
        """
        return self.session is not None and self.session.validate()

    async def login(self, login_routine: Callable) -> bool:
        """Attempt to log in to the CTF platform using the platform-specific login
        routine if the current session is unauthorized.

        Args:
            login_routine: The function that handles the login routine.

        Returns:
            A boolean representing whether we've been authorized.
        """
        if not self.is_authorized():
            self.session = await login_routine(self)

        return self.is_authorized()


class PlatformABC(ABC):
    """An abstract base class representing a CTF platform.

    Author:
        @es3n1n

    Notes:
        If some methods return None instead of the result, it means that
        something went horribly wrong within the communication logic, it might be worth
        to try again.
    """

    @classmethod
    @abstractmethod
    async def match_platform(cls, ctx: PlatformCTX) -> bool:
        pass

    @classmethod
    @abstractmethod
    async def login(cls, ctx: PlatformCTX) -> Optional[Session]:
        pass

    @classmethod
    @abstractmethod
    async def submit_flag(
        cls, ctx: PlatformCTX, challenge_id: str, flag: str
    ) -> Optional[SubmittedFlag]:
        pass

    @classmethod
    @abstractmethod
    async def pull_challenges(cls, ctx: PlatformCTX) -> AsyncIterator[Challenge]:
        pass

    @classmethod
    @abstractmethod
    async def pull_scoreboard(
        cls, ctx: PlatformCTX, max_entries_count: int = 20
    ) -> AsyncIterator[Team]:
        # @note: @es3n1n:
        # https://stackoverflow.com/a/68911014
        yield Team(id="", name="")

    @classmethod
    @abstractmethod
    async def register(cls, ctx: PlatformCTX) -> RegistrationStatus:
        pass

    @classmethod
    @abstractmethod
    async def get_challenge(
        cls, ctx: PlatformCTX, challenge_id: str
    ) -> Optional[Challenge]:
        pass

    @classmethod
    @abstractmethod
    async def pull_challenge_solvers(
        cls, ctx: PlatformCTX, challenge_id: str, limit: int = 10
    ) -> AsyncIterator[ChallengeSolver]:
        # @note: @es3n1n:
        # https://stackoverflow.com/a/68911014
        yield ChallengeSolver(team=Team(id="", name=""), solved_at=datetime.utcnow())

    @classmethod
    @abstractmethod
    async def get_me(cls, ctx: PlatformCTX) -> Optional[Team]:
        pass
