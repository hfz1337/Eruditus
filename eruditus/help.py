help_info = {
    "ctf": {
        "createctf": {
            "name": "createctf",
            "aliases": ["newctf", "addctf", "mkctf"],
            "usage": "{}ctf <createctf|newctf|addctf|mkctf> <ctf_name>",
            "brief": "Creates a new CTF.",
            "help": "Creates a new CTF, as well as a new category channel and role for it.",
        },
        "renamectf": {
            "name": "renamectf",
            "aliases": [],
            "usage": "{}ctf renamectf <new_ctf_name>",
            "brief": "Renames the current CTF.",
            "help": (
                "Renames the current CTF, this must be run in one of the channels of the CTF you wish to rename."
            ),
        },
        "archivectf": {
            "name": "archivectf",
            "aliases": ["archive"],
            "usage": "{}ctf archivectf [<mode>] [<ctf_name>]",
            "brief": "Archives a CTF.",
            "help": (
                "Makes the CTF channels read-only and opens them for everyone in the guild.\n"
                "Available modes are:\n"
                "**minimal (default):** archives the notes channel only.\n"
                "**all:** archives all channels.\n\n"
                "If `ctf_name` is not provided, it defaults to the CTF associated which the channel from which the command is run."
            ),
        },
        "deletectf": {
            "name": "deletectf",
            "aliases": ["removectf", "delctf", "rmctf"],
            "usage": "{}ctf <deletectf|removectf|delctf|rmctf> [<ctf_name>]",
            "brief": "Deletes a CTF.",
            "help": (
                "Deletes a CTF as well as its respective role and channels.\n"
                "If `ctf_name` is not provided, it defaults to the CTF associated which the channel from which the command is run."
            ),
        },
        "join": {
            "name": "join",
            "aliases": [],
            "usage": "{}ctf join <ctf_name>",
            "brief": "Join and ongoing CTF competition.",
            "help": "Join and ongoing CTF competition.",
        },
        "leave": {
            "name": "leave",
            "aliases": [],
            "usage": "{}ctf leave",
            "brief": "Leave the current CTF.",
            "help": "Leave the CTF competition associated which the channel from which the command is run.",
        },
        "addcreds": {
            "name": "addcreds",
            "aliases": ["setcreds"],
            "usage": "{}ctf <addcreds|setcreds> <username> <password> <url>",
            "brief": "Adds credentials for a CTF.",
            "help": "Adds credentials for the CTF associated which the category channel from which the command is run in a new read-only channel called `credentials`.",
        },
        "showcreds": {
            "name": "showcreds",
            "aliases": ["getcreds", "creds"],
            "usage": "{}ctf <showcreds|getcreds|creds>",
            "brief": "Shows credentials of a CTF.",
            "help": "Show credentials of the CTF associated which the category channel from which the command is run.",
        },
        "status": {
            "name": "status",
            "aliases": [],
            "usage": "{}ctf status [<ctf_name>]",
            "brief": "Display CTF status.",
            "help": (
                "Show status of a specific CTF."
                "If `ctf_name` is not provided, it defaults to the CTF associated with the category channel from which the command is run.\n"
                "If `ctf_name` is not provided and the command is invoked from outside a CTF category channel, it displays all ongoing CTF competitions.\n\n"
            ),
        },
        "workon": {
            "name": "workon",
            "aliases": [],
            "usage": "{}ctf workon <challenge_name>",
            "brief": "Shows that you're working on a challenge, and adds you to its associated channel.",
            "help": (
                "Shows that you're working on a challenge, and adds you to its associated channel."
            ),
        },
        "unworkon": {
            "name": "unworkon",
            "aliases": [],
            "usage": "{}ctf unworkon [<challenge_name>]",
            "brief": "Stop working on a challenge.",
            "help": (
                "Stop working on a challenge and leave the associated channel.\n"
                "If `challenge_name` is not provided, it defaults to the challenge associated which the channel from which the command is run."
            ),
        },
        "solve": {
            "name": "solve",
            "aliases": [],
            "usage": "{}ctf solve [<support_member>]...",
            "brief": "Marks a challenge as solved.",
            "help": (
                "Marks the challenge associated which the channel from which the command is run as solved by "
                "the member invoking the command and the one or multiple support members specified in `support_member`."
            ),
        },
        "unsolve": {
            "name": "unsolve",
            "aliases": [],
            "usage": "{}ctf unsolve",
            "brief": "Marks a challenge as not solved.",
            "help": (
                "Marks the challenge associated which the channel from which the command is run as not solved."
            ),
        },
        "createchallenge": {
            "name": "createchallenge",
            "aliases": ["addch", "newch"],
            "usage": "{}ctf <createchallenge|addch|newch> <challenge_name> <challenge_category>",
            "brief": "Adds a new challenge for the current CTF.",
            "help": "Adds a new challenge for the current CTF, and creates a new channel and role for it.",
        },
        "renamechallenge": {
            "name": "renamechallenge",
            "aliases": ["renamech"],
            "usage": "{}ctf <renamechallenge|renamech> <new_name> [<new_category>]",
            "brief": "Renames a challenge.",
            "help": (
                "Renames the challenge associated which the channel from which the command is run, and eventually its category name."
            ),
        },
        "deletechallenge": {
            "name": "deletechallenge",
            "aliases": ["rmch", "delch"],
            "usage": "{}ctf <deletechallenge|rmch|delch> [<challenge_name>]",
            "brief": "Deletes a challenge from the CTF.",
            "help": (
                "Deletes a challenge from the CTF as well as its respective channel and role.\n"
                "If `challenge_name` is not provided, it defaults to the challenge associated which the channel from which the command is run."
            ),
        },
        "pull": {
            "name": "pull",
            "aliases": [],
            "usage": "{}ctf pull [<ctfd_url>]",
            "brief": "Pulls challenges from the CTFd platform.",
            "help": (
                "Pulls challenges from the CTFd platform hosted at `ctfd_url`.\n"
                "If `ctfd_url` is not provided, it defaults to the URL that was setup along with the credentials."
            ),
        },
        "takenote": {
            "name": "takenote",
            "aliases": ["highlight", "hl"],
            "usage": "{}ctf <takenote|highlight|hl> <type> [<note_format>]",
            "brief": "Copies the last message into the #notes channel.",
            "help": (
                "Copies the last message into the #notes channel.\n"
                "Available types are:\n"
                "**progress:** highlights a challenge progress (must be used from within a CTF challenge channel).\n"
                "**info|note:** highlights an important information, resource or whatever.\n\n"
                "`note_format` can be either **embed** or **raw**."
            ),
        },
    },
    "ctftime": {
        "upcoming": {
            "name": "upcoming",
            "aliases": [],
            "usage": "{}ctftime upcoming [<limit>]",
            "brief": "Show upcoming events.",
            "help": (
                "Shows upcoming events.\n"
                "In case `limit` is not provided, the default value is 3."
            ),
        },
        "current": {
            "name": "current",
            "aliases": ["now", "running", "ongoing"],
            "usage": "{}ctftime <current|now|running|ongoing>",
            "brief": "Shows ongoing CTF competitions.",
            "help": "Shows ongoing CTF competitions.",
        },
        "top": {
            "name": "top",
            "aliases": [],
            "usage": "{}ctftime top [<year>]",
            "brief": "Shows CTFTime's leaderboard for a specific year.",
            "help": (
                "Shows CTFTime's leaderboard for a specific year.\n"
                "In case `year` is not provided, it defaults to the current year."
            ),
        },
    },
    "syscalls": {
        "available": {
            "name": "available",
            "aliases": [],
            "usage": "{}syscalls available",
            "brief": "Shows the available syscall architectures.",
            "help": "Shows the available syscall architectures.",
        },
        "show": {
            "name": "show",
            "aliases": [],
            "usage": "{}syscalls show <arch> <syscall_name/syscall_id>",
            "brief": "Shows information for a specific syscall.",
            "help": (
                "Shows information for a specific syscall.\n"
                "In case a syscall id is provided, it can be either in decimal or in hex, when the latter is used it should be prefixed with `0x`."
            ),
        },
    },
    "cipher": {
        "caesar": {
            "name": "caesar",
            "aliases": [],
            "usage": "{}cipher caesar <message> [<key>]",
            "brief": "Encrypts/Decrypts a message using Caesar.",
            "help": (
                "Encrypts/Decrypts a message using Caesar.\n"
                "If `key` is not provided, every possible key is tried."
            ),
        },
        "rot13": {
            "name": "rot13",
            "aliases": [],
            "usage": "{}cipher rot13 <message>",
            "brief": "Encrypts/Decrypts a message using Rot13.",
            "help": (
                "Encrypts/Decrypts a message using Rot13, similar to running `!cipher caesar <message> 13`."
            ),
        },
        "atbash": {
            "name": "atbash",
            "aliases": [],
            "usage": "{}cipher atbash <message>",
            "brief": "Encrypts/Decrypts a message using atbash.",
            "help": "Encrypts/Decrypts a message using atbash.",
        },
    },
    "encoding": {
        "base64": {
            "name": "base64",
            "aliases": [],
            "usage": "{}encoding base64 <encode/decode> <data>",
            "brief": "Encodes/Decodes `data` using base64.",
            "help": "Encodes/Decodes `data` using base64.",
        },
        "base32": {
            "name": "base32",
            "aliases": [],
            "usage": "{}encoding base32 <encode/decode> <data>",
            "brief": "Encodes/Decodes `data` using base32.",
            "help": "Encodes/Decodes `data` using base32.",
        },
        "binary": {
            "name": "binary",
            "aliases": [],
            "usage": "{}encoding binary <encode/decode> <data>",
            "brief": "Encodes/Decodes `data` to/from binary.",
            "help": "Encodes/Decodes `data` to/from binary.",
        },
        "url": {
            "name": "url",
            "aliases": [],
            "usage": "{}encoding url <encode/decode> <data>",
            "brief": "URL encoding/decoding.",
            "help": "URL encoding/decoding.",
        },
    },
}
