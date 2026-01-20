import os
import random
from pathlib import Path
from typing import Callable, Optional, TypeVar

import dotenv
from pymongo import MongoClient

T = TypeVar("T")
dotenv.load_dotenv()


class RandomUserAgent:
    """A class that represents a random User-Agent."""

    def __init__(self) -> None:
        user_agents_path = Path(__file__).parent / "assets" / "user-agents.txt"
        with open(user_agents_path, encoding="utf-8") as f:
            self.user_agents = [line.strip() for line in f.readlines()]

    def __call__(self) -> str:
        return random.choice(self.user_agents)


def load_revision() -> str:
    """Get the current revision.

    Notes:
        We start by looking up the `.revision` file, if it's present, we use it.
        Otherwise, we try using the `.git` folder by reading `refs/heads/master`.
    """
    root_dir: Path = Path(__file__).parent
    dot_revision: Path = root_dir / ".revision"

    if dot_revision.exists():
        with open(dot_revision, encoding="utf-8") as f:
            return f.read().strip()

    git_dir: Path = root_dir.parent / ".git"

    head_ref: Path = git_dir / "refs" / "heads" / "master"
    if head_ref.exists():
        with open(head_ref, encoding="utf-8") as f:
            return f.read().strip()

    return "unknown"


def load_nullable_env_var(
    name: str, factory: Callable[[str], T] = lambda x: x, default: Optional[T] = None
) -> Optional[T]:
    """Load a nullable config var."""
    var = os.getenv(name)
    return default if not var else factory(var)


# fmt: off
# flake8: noqa
CHALLENGE_COLLECTION = os.getenv("CHALLENGE_COLLECTION", "challenges")
CTF_COLLECTION = os.getenv("CTF_COLLECTION", "ctfs")
CTFTIME_URL = os.getenv("CTFTIME_URL", "https://ctftime.org")
DATE_FORMAT = os.getenv("DATE_FORMAT", "%Y-%m-%d %H:%M")
DBNAME = os.getenv("DBNAME", "eruditus")
DEVELOPER_USER_ID = os.getenv("DEVELOPER_USER_ID")
GUILD_ID = load_nullable_env_var("GUILD_ID", factory=int, default=0)
MAX_CONTENT_SIZE = int(os.getenv("MAX_CONTENT_SIZE", "2000"))
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
USER_AGENT = RandomUserAgent()
WRITEUP_INDEX_API = os.getenv("WRITEUP_INDEX_API")
TEAM_NAME = os.getenv("TEAM_NAME", "Eruditus")
TEAM_EMAIL = os.getenv("TEAM_EMAIL", "team@example.com")
MIN_PLAYERS = int(os.getenv("MIN_PLAYERS", "1"))
COMMIT_HASH = load_revision()
BOOKMARK_CHANNEL = load_nullable_env_var("BOOKMARK_CHANNEL", factory=int)
REMINDER_CHANNEL = load_nullable_env_var("REMINDER_CHANNEL", factory=int)
CTFTIME_TEAM_ID = load_nullable_env_var("CTFTIME_TEAM_ID", factory=int)
CTFTIME_TRACKING_CHANNEL = load_nullable_env_var("CTFTIME_TRACKING_CHANNEL", factory=int)
CTFTIME_LEADERBOARD_CHANNEL = load_nullable_env_var("CTFTIME_LEADERBOARD_CHANNEL", factory=int)

MONGO = MongoClient(MONGODB_URI)
