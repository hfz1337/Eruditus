import os
from pathlib import Path
from typing import Callable, Optional, TypeVar

import dotenv
from pymongo import MongoClient

T = TypeVar("T")
dotenv.load_dotenv()


def load_revision() -> str:
    """Get the current revision.

    Author:
        @es3n1n (refactoring and handling of multiple cases)

    Notes:
        We start by looking up the `.revision` file, if it's present, we use it.
        Otherwise, we try using the `.git` folder by reading `refs/heads/master`.
    """
    root_dir: Path = Path(__file__).parent
    dot_revision: Path = root_dir / ".revision"

    if dot_revision.exists():
        return open(dot_revision, encoding="utf-8").read()

    git_dir: Path = root_dir.parent / ".git"

    head_ref: Path = git_dir / "refs" / "heads" / "master"
    if head_ref.exists():
        return open(head_ref, encoding="utf-8").read()

    return "unknown"


def load_nullable_env_var(
    name: str, factory: Callable[[str], T] = lambda x: x
) -> Optional[T]:
    """Load the nullable config var.

    Author:
        @es3n1n
    """
    var = os.getenv(name)
    if not var:
        return var

    return factory(var)


CHALLENGE_COLLECTION = os.getenv("CHALLENGE_COLLECTION")
CTF_COLLECTION = os.getenv("CTF_COLLECTION")
CTFTIME_URL = os.getenv("CTFTIME_URL")
DATE_FORMAT = os.getenv("DATE_FORMAT")
DBNAME = os.getenv("DBNAME")
DEVELOPER_USER_ID = os.getenv("DEVELOPER_USER_ID")
GUILD_ID = int(os.getenv("GUILD_ID"))
MAX_CONTENT_SIZE = int(os.getenv("MAX_CONTENT_SIZE"))
MONGODB_URI = os.getenv("MONGODB_URI")
USER_AGENT = os.getenv("USER_AGENT")
WRITEUP_INDEX_API = os.getenv("WRITEUP_INDEX_API")
TEAM_NAME = os.getenv("TEAM_NAME")
TEAM_EMAIL = os.getenv("TEAM_EMAIL")
MIN_PLAYERS = int(os.getenv("MIN_PLAYERS"))
COMMIT_HASH = load_revision()
REMINDER_CHANNEL = load_nullable_env_var("REMINDER_CHANNEL", factory=int)
BOOKMARK_CHANNEL = int(os.getenv("BOOKMARK_CHANNEL"))
CTFTIME_TEAM_ID = load_nullable_env_var("CTFTIME_TEAM_ID", factory=int)
CTFTIME_TRACKING_CHANNEL = load_nullable_env_var(
    "CTFTIME_TRACKING_CHANNEL", factory=int
)

MONGO = MongoClient(MONGODB_URI)
