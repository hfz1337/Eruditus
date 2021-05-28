from discord_slash.model import SlashCommandOptionType as OptionType

cog_help = {
    "name": "cipher",
    "description": "Encryption/Decryption using classic ciphers",
    "subcommands": {
        "caesar": {
            "name": "caesar",
            "description": "Caesar cipher",
            "options": [
                {
                    "name": "message",
                    "description": "The message to encrypt/decrypt",
                    "option_type": OptionType.STRING,
                    "required": True,
                },
                {
                    "name": "key",
                    "description": (
                        "The key to encrypt/decrypt with (default: brute-force)"
                    ),
                    "option_type": OptionType.INTEGER,
                    "required": False,
                },
            ],
        },
        "rot13": {
            "name": "rot13",
            "description": "Rot13 cipher",
            "options": [
                {
                    "name": "message",
                    "description": "The message to encrypt/decrypt",
                    "option_type": OptionType.STRING,
                    "required": True,
                }
            ],
        },
        "atbash": {
            "name": "atbash",
            "description": "Atbash cipher",
            "options": [
                {
                    "name": "message",
                    "description": "The message to encrypt/decrypt",
                    "option_type": OptionType.STRING,
                    "required": True,
                }
            ],
        },
    },
}
