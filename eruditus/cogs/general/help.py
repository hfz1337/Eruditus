from discord_slash.model import SlashCommandOptionType as OptionType

cog_help = {
    "commands": {
        "help": {
            "name": "help",
            "description": "Get help about the bot usage",
            "options": [],
        },
        "config": {
            "name": "config",
            "description": "Change configuration variables",
            "options": [
                {
                    "name": "minimum_player_count",
                    "description": (
                        "The minimum number of players required to create a CTF "
                        "automatically"
                    ),
                    "option_type": OptionType.INTEGER,
                    "required": False,
                },
                {
                    "name": "voting_starts_countdown",
                    "description": (
                        "The number of seconds remaining for a CTF to start when we "
                        "announce it for voting"
                    ),
                    "option_type": OptionType.INTEGER,
                    "required": False,
                },
                {
                    "name": "voting_verdict_countdown",
                    "description": (
                        "The number of seconds before the CTF starts from which we "
                        "start considering the votes"
                    ),
                    "option_type": OptionType.INTEGER,
                    "required": False,
                },
            ],
        },
        "request": {
            "name": "request",
            "description": "Request a new feature from the developer",
            "options": [
                {
                    "name": "feature",
                    "description": "Description of the new feature you want to suggest",
                    "option_type": OptionType.STRING,
                    "required": True,
                },
            ],
        },
        "report": {
            "name": "report",
            "description": "Report a bug to the developer",
            "options": [
                {
                    "name": "bug",
                    "description": "Description of the bug you encountered",
                    "option_type": OptionType.STRING,
                    "required": True,
                },
            ],
        },
        "search": {
            "name": "search",
            "description": "Search for a topic in the CTF write-ups index",
            "options": [
                {
                    "name": "query",
                    "description": (
                        "The search query. Use double quotes for exact matches, and "
                        'prepend a term with a "-" to exclude it'
                    ),
                    "option_type": OptionType.STRING,
                    "required": True,
                },
                {
                    "name": "limit",
                    "description": "Number of results to display (default: 3)",
                    "option_type": OptionType.INTEGER,
                    "required": False,
                },
            ],
        },
    },
}
