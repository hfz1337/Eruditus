from discord_slash.model import SlashCommandOptionType as OptionType

cog_help = {
    "name": "ctf",
    "description": "Manage CTF creation, deletion, and more",
    "subcommands": {
        "createctf": {
            "name": "createctf",
            "description": "Creates a new CTF",
            "options": [
                {
                    "name": "name",
                    "description": "CTF name",
                    "option_type": OptionType.STRING,
                    "required": True,
                },
            ],
        },
        "renamectf": {
            "name": "renamectf",
            "description": "Renames the current CTF",
            "options": [
                {
                    "name": "new_name",
                    "description": "New CTF name",
                    "option_type": OptionType.STRING,
                    "required": True,
                },
            ],
        },
        "archivectf": {
            "name": "archivectf",
            "description": "Archives a CTF",
            "options": [
                {
                    "name": "mode",
                    "description": (
                        "Whether to archive all the channels, or the important ones "
                        "only (default: minimal)"
                    ),
                    "option_type": OptionType.STRING,
                    "required": False,
                    "choices": ["minimal", "all"],
                },
                {
                    "name": "name",
                    "description": "CTF name (default: current channel's CTF)",
                    "option_type": OptionType.STRING,
                    "required": False,
                },
            ],
        },
        "deletectf": {
            "name": "deletectf",
            "description": "Deletes a CTF",
            "options": [
                {
                    "name": "name",
                    "description": (
                        "Name of the CTF to delete (default: current channel's CTF)"
                    ),
                    "option_type": OptionType.STRING,
                    "required": False,
                },
            ],
        },
        "join": {
            "name": "join",
            "description": "Join and ongoing CTF competition",
            "options": [
                {
                    "name": "name",
                    "description": "Name of the CTF to join",
                    "option_type": OptionType.STRING,
                    "required": True,
                },
            ],
        },
        "leave": {
            "name": "leave",
            "description": "Leave the current CTF",
            "options": [],
        },
        "addcreds": {
            "name": "addcreds",
            "description": "Adds credentials for the current CTF",
            "options": [
                {
                    "name": "username",
                    "description": "The username to login with",
                    "option_type": OptionType.STRING,
                    "required": True,
                },
                {
                    "name": "password",
                    "description": "The password to login with",
                    "option_type": OptionType.STRING,
                    "required": True,
                },
                {
                    "name": "url",
                    "description": "URL of the CTF platform",
                    "option_type": OptionType.STRING,
                    "required": True,
                },
            ],
        },
        "showcreds": {
            "name": "showcreds",
            "description": "Show credentials of the current CTF",
            "options": [],
        },
        "status": {
            "name": "status",
            "description": "Display CTF status",
            "options": [
                {
                    "name": "name",
                    "description": (
                        "CTF name (default: current channel's CTF, or all ongoing CTF "
                        "competitions)"
                    ),
                    "option_type": OptionType.STRING,
                    "required": False,
                },
            ],
        },
        "workon": {
            "name": "workon",
            "description": (
                "Shows that you're working on a challenge, and adds you to its "
                "associated channel"
            ),
            "options": [
                {
                    "name": "name",
                    "description": "Challenge name (case sensitive)",
                    "option_type": OptionType.STRING,
                    "required": True,
                },
            ],
        },
        "unworkon": {
            "name": "unworkon",
            "description": (
                "Stop working on a challenge and leave its channel (default: current "
                "channel's challenge"
            ),
            "options": [
                {
                    "name": "name",
                    "description": "Challenge name (case sensitive)",
                    "option_type": OptionType.STRING,
                    "required": False,
                },
            ],
        },
        "solve": {
            "name": "solve",
            "description": (
                "Marks the challenge as solved by you, and eventually up to 4 support"
                "members that helped you"
            ),
            "options": [
                {
                    "name": f"support{i}",
                    "description": (
                        "Support member who contributed solving the challenge"
                    ),
                    "option_type": OptionType.USER,
                    "required": False,
                }
                for i in range(1, 5)
            ],
        },
        "unsolve": {
            "name": "unsolve",
            "description": "Marks the challenge as not solved",
            "options": [],
        },
        "createchallenge": {
            "name": "createchallenge",
            "description": "Adds a new challenge for the current CTF",
            "options": [
                {
                    "name": "name",
                    "description": "Name of the challenge",
                    "option_type": OptionType.STRING,
                    "required": True,
                },
                {
                    "name": "category",
                    "description": "Category of the challenge",
                    "option_type": OptionType.STRING,
                    "required": True,
                },
            ],
        },
        "renamechallenge": {
            "name": "renamechallenge",
            "description": "Renames a challenge",
            "options": [
                {
                    "name": "new_name",
                    "description": "New challenge name",
                    "option_type": OptionType.STRING,
                    "required": True,
                },
                {
                    "name": "new_category",
                    "description": "New challenge category",
                    "option_type": OptionType.STRING,
                    "required": False,
                },
            ],
        },
        "deletechallenge": {
            "name": "deletechallenge",
            "description": "Deletes a challenge from the CTF",
            "options": [
                {
                    "name": "name",
                    "description": (
                        "Name of the challenge to delete (default: current channel's "
                        "challenge)"
                    ),
                    "option_type": OptionType.STRING,
                    "required": False,
                }
            ],
        },
        "pull": {
            "name": "pull",
            "description": "Pulls challenges from the CTFd platform",
            "options": [
                {
                    "name": "ctfd_url",
                    "description": (
                        "URL of the CTFd platform (default: url from the previously "
                        "configured credentials)"
                    ),
                    "option_type": OptionType.STRING,
                    "required": False,
                }
            ],
        },
        "takenote": {
            "name": "takenote",
            "description": "Copies the last message into the #notes channel",
            "options": [
                {
                    "name": "note_type",
                    "description": (
                        "Whether the note is about a challenge progress or otherwise"
                    ),
                    "option_type": OptionType.STRING,
                    "required": True,
                    "choices": ["progress", "info"],
                },
                {
                    "name": "note_format",
                    "description": (
                        "Whether to create an embed for the note or take it as is "
                        "(default: embed)"
                    ),
                    "option_type": OptionType.STRING,
                    "required": False,
                    "choices": ["embed", "raw"],
                },
            ],
        },
        "submit": {
            "name": "submit",
            "description": "Submit a flag to the CTFd platform",
            "options": [
                {
                    "name": "flag",
                    "description": "Flag of the challenge",
                    "option_type": OptionType.STRING,
                    "required": True,
                }
            ]
            + [
                {
                    "name": f"support{i}",
                    "description": (
                        "Support member who contributed solving the challenge"
                    ),
                    "option_type": OptionType.USER,
                    "required": False,
                }
                for i in range(1, 5)
            ],
        },
        "scoreboard": {
            "name": "scoreboard",
            "description": "Display scoreboard for the CTF",
            "options": [],
        },
    },
}
