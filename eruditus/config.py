########################################################################################
# Required configuration variables
########################################################################################
DISCORD_TOKEN = "BOT_TOKEN_GOES_HERE"
MONGODB_URI = "mongodb://mongodb:27017/"
DBNAME = "eruditus"
CTFTIME_EVENTS_COLLECTION = "ctftime"
CTFS_COLLECTION = "ctfs"
CHANNELS_COLLECTION = "channels"
DATE_FORMAT = "%a, %d %B %Y, %H:%M UTC"
CTFTIME_URL = "https://ctftime.org"
# CTFtime's nginx server is configured to block requests with specific
# user agents, like those containing "python-requests".
USER_AGENT = "Eruditus"
# The minimum number of players required to create a CTF automatically
MINIMUM_PLAYER_COUNT = 5
# The number of seconds before the CTF starts from which we start considering
# the votes to decide whether to create the CTF or not (required, default: 2 hours)
VOTING_VERDICT_COUNTDOWN = 7200
# The number of seconds remaining for a CTF to start when we announce it for
# voting (required, default: 2 days)
VOTING_STARTS_COUNTDOWN = 172800

########################################################################################
# Optional configuration variables, will be decided by the bot if left None
########################################################################################
# The category channel where past CTFs results will be moved
ARCHIVE_CATEGORY_CHANNEL = None
# The channel ID where we make CTF announcements and enable voting (optional)
EVENT_ANNOUNCEMENT_CHANNEL = None
