import os
import dotenv

from pymongo import MongoClient

dotenv.load_dotenv()

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

MONGO = MongoClient(MONGODB_URI)
