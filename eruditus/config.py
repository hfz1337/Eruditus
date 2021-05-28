########################################################################################
# CONSTANTS
########################################################################################
MONGODB_URI = "mongodb://mongodb:27017/"
DBNAME = "eruditus"
CTFTIME_COLLECTION = "ctftime"
CHALLENGE_COLLECTION = "challenge"
CTF_COLLECTION = "ctf"
CONFIG_COLLECTION = "config"
DATE_FORMAT = "%a, %d %B %Y, %H:%M UTC"
CTFTIME_URL = "https://ctftime.org"
# CTFtime's nginx server is configured to block requests with specific
# user agents, like those containing "python-requests"
USER_AGENT = "Eruditus"

########################################################################################
# Required configuration variables
########################################################################################
# The minimum number of players required to create a CTF automatically
MINIMUM_PLAYER_COUNT = 5
# The number of seconds before the CTF starts from which we start considering
# the votes to decide whether to create the CTF or not (default: 2 hours)
VOTING_VERDICT_COUNTDOWN = 7200
# The number of seconds remaining for a CTF to start when we announce it for
# voting (default: 2 days)
VOTING_STARTS_COUNTDOWN = 172800

########################################################################################
# Optional configuration variables, will be decided by the bot if left None
########################################################################################
# The category channel where past CTFs results will be moved
ARCHIVE_CATEGORY_CHANNEL = None
# The channel ID where we make CTF announcements and enable voting
ANNOUNCEMENT_CHANNEL = None
