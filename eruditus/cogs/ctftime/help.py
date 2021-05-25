from discord_slash.model import SlashCommandOptionType as OptionType

cog_help = {
    "name": "ctftime",
    "description": "Gather information from CTFtime",
    "subcommands": {
        "current": {
            "name": "current",
            "description": "Show ongoing CTF competitions",
            "options": [],
        },
        "upcoming": {
            "name": "upcoming",
            "description": "Show upcoming events",
            "options": [
                {
                    "name": "limit",
                    "description": "Number of events to fetch (default: 3)",
                    "option_type": OptionType.INTEGER,
                    "required": False,
                },
            ],
        },
        "top": {
            "name": "top",
            "description": (
                "Shows CTFTime's leaderboard for a specific year "
                "(default: current year)"
            ),
            "options": [
                {
                    "name": "year",
                    "description": "Leaderboard's year",
                    "option_type": OptionType.INTEGER,
                    "required": False,
                },
            ],
        },
    },
}
