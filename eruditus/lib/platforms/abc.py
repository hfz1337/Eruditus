from abc import ABC
from abc import abstractmethod
from dataclasses import dataclass
from dataclasses import field
from enum import IntEnum
from enum import auto
from enum import unique
from typing import Any
from typing import Dict
from typing import Generator
from typing import List
from typing import Optional


# @todo: @es3n1n: move the dataclasses outside of this file


# A session representation, contains stuff like cookies
@dataclass
class Session:
    token: Optional[str] = None
    cookies: Dict[str, str] = field(default_factory=dict)

    def validate(self) -> bool:
        return len(self.cookies) > 0 or self.token is not None


# Challenge attachment repr
@dataclass
class ChallengeFile:
    url: str
    name: Optional[str] = None


# A challenge representation, perhaps we should store some more info though
@dataclass
class Challenge:
    # Please note that we are storing id as str (bcs of UUIDs and others), so please don't forget
    # to convert it to the right type before sending it to the platform backend
    id: str

    name: Optional[str] = None
    value: Optional[int] = None
    description: Optional[str] = None
    connection_info: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[str] = None
    files: Optional[List[ChallengeFile]] = None
    solves: Optional[int] = None


# Submitted flag state representation
@unique
class SubmittedFlagState(IntEnum):
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


# Retries representation
@dataclass
class Retries:
    left: int
    out_of: Optional[int] = None


# Submitted flag representation
@dataclass
class SubmittedFlag:
    state: SubmittedFlagState
    retries: Optional[Retries] = None
    is_first_blood: bool = False

    # Automatically update `is_first_blood`
    async def update_first_blood(self, ctx: 'PlatformCTX', challenge_getter, challenge_id: str, checker) -> None:
        # Skip invalid flags
        if self.state != SubmittedFlagState.CORRECT:
            self.is_first_blood = False
            return

        # Querying challenge
        challenge: Optional['Challenge'] = await challenge_getter(ctx, challenge_id)
        if not challenge or challenge.solves is None:
            self.is_first_blood = False
            return

        # Updating is_first_blood
        self.is_first_blood = checker(challenge.solves)


# Team representation
@dataclass
class Team:
    name: str
    score: Optional[int] = None
    invite_token: Optional[str] = None  # (used only for rCTF)
    solves: Optional[List[Challenge]] = None  # (used only for rCTF)


# Registration status repr
@dataclass
class RegistrationStatus:
    success: bool
    message: Optional[str] = None
    token: Optional[str] = None  # (used only for rCTF)
    invite: Optional[str] = None  # (used only for rCTF)


# A basic context representation
@dataclass
class PlatformCTX:
    # @note: @es3n1n: These are required fields
    base_url: str

    # @note: @es3n1n: A custom set of arguments, such as:
    # * email
    # * login
    # * password
    # * token
    # * etc
    # None of these are required by default and everything should be
    # checked within the platform itself
    #
    # @todo: @es3n1n: ideally we should have some stuff that would validate it
    # automatically (pydantic?)
    args: Dict[str, str] = field(default_factory=dict)

    # @note: @es3n1n: Session that would be updated within the function
    session: Optional[Session] = None

    # @note: @es3n1n: Some set of utils
    @property
    def url_stripped(self) -> str:
        return self.base_url.strip('/')

    def get_args(self, *required_fields: str, **kwargs: str) -> Dict[str, str]:
        result: Dict[str, str] = {key: value for key, value in self.args.items() if key in required_fields}

        for k, v in kwargs.items():
            result[k] = v

        return result

    # Returns true if valid
    def validate_arg(self, key: str, *invalid_values: Any) -> bool:
        if key not in self.args:
            return False

        return self.args not in invalid_values

    def is_authorized(self) -> bool:
        return self.session is not None and self.session.validate()

    async def login(self, cb) -> bool:
        if not self.is_authorized():
            self.session = await cb(self)

        return self.is_authorized()

    # Custom ctor
    @staticmethod
    def from_credentials(credentials: Dict[str, str]) -> 'PlatformCTX':
        return PlatformCTX(
            base_url=credentials['url'],
            args=credentials,
        )


# Platform abstract interface
# @note: @es3n1n: if some of the methods returns None instead of the result that means that there's something
# that went horribly wrong within the communication logic, might be worth to try again
#
class PlatformABC(ABC):
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
    async def submit_flag(cls, ctx: PlatformCTX, challenge_id: str, flag: str) -> Optional[SubmittedFlag]:
        pass

    @classmethod
    @abstractmethod
    async def pull_challenges(cls, ctx: PlatformCTX) -> Generator[Challenge, None, None]:
        pass

    @classmethod
    @abstractmethod
    async def pull_scoreboard(cls, ctx: PlatformCTX, max_entries_count: int = 20) -> Generator[Team, None, None]:
        pass

    @classmethod
    @abstractmethod
    async def register(cls, ctx: PlatformCTX) -> RegistrationStatus:
        pass

    @classmethod
    @abstractmethod
    async def get_challenge(cls, ctx: PlatformCTX, challenge_id: str) -> Optional[Challenge]:
        pass
