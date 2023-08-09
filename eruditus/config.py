import os
import dotenv

from pathlib import Path
from pymongo import MongoClient

dotenv.load_dotenv()


def load_revision() -> str:
    # @note: @es3n1n: Obtaining paths to the revision and .git
    root_dir: Path = Path(__file__).parent
    dot_revision: Path = root_dir / ".revision"

    # @note: @es3n1n: If there's a .revision file then we should
    # use it
    if dot_revision.exists():
        return open(dot_revision).read()

    # @note: @es3n1n: If not we should try to use the .git folder
    # instead
    git_dir: Path = root_dir.parent / ".git"

    # @note: @es3n1n: If head ref is available then we should use it
    head_ref: Path = git_dir / "refs" / "heads" / "master"
    if head_ref.exists():
        return open(head_ref).read()

    # @note: @es3n1n: :shrug:
    return "unknown"


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
REMINDER_CHANNEL = (
    int(os.getenv("REMINDER_CHANNEL")) if os.getenv("REMINDER_CHANNEL") else None
)
OPENAI_URL = os.getenv("OPENAI_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_GPT_MODEL = os.getenv("OPENAI_GPT_MODEL")
BOOKMARK_CHANNEL = int(os.getenv("BOOKMARK_CHANNEL"))

MONGO = MongoClient(MONGODB_URI)
