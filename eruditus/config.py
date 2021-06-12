########################################################################################
# CONSTANTS
########################################################################################
MONGODB_URI = "mongodb://mongodb:27017/"
DBNAME_PREFIX = "eruditus"
CTFTIME_COLLECTION = "ctftime"
CHALLENGE_COLLECTION = "challenge"
CTF_COLLECTION = "ctf"
CONFIG_COLLECTION = "config"
DATE_FORMAT = "%a, %d %B %Y, %H:%M UTC"
CTFTIME_URL = "https://ctftime.org"
WRITEUP_INDEX_API = "http://ctf.hfz-1337.ninja"
DEVELOPER_USER_ID = 305076601253789697
# CTFtime's nginx server is configured to block requests with specific
# user agents, like those containing "python-requests"
USER_AGENT = "Eruditus"

########################################################################################
# Required configuration variables, can be changed later using a command
########################################################################################
# The minimum number of players required to create a CTF automatically
MINIMUM_PLAYER_COUNT = 5
# The number of seconds remaining for a CTF to start when we announce it for
# voting (default: 2 days)
VOTING_STARTS_COUNTDOWN = 172800
# The number of seconds before the CTF starts from which we start considering
# the votes to decide whether to create the CTF or not (default: 2 hours)
VOTING_VERDICT_COUNTDOWN = 7200
