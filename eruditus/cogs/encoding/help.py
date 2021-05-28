from discord_slash.model import SlashCommandOptionType as OptionType

cog_help = {
    "name": "encoding",
    "description": "Simple encoding/decoding utility",
    "subcommands": {
        "base64": {
            "name": "base64",
            "description": "Base64 encoding/decoding",
            "options": [
                {
                    "name": "mode",
                    "description": "Operation mode",
                    "option_type": OptionType.STRING,
                    "required": True,
                    "choices": ["encode", "decode"],
                },
                {
                    "name": "data",
                    "description": "The data to encode or decode",
                    "option_type": OptionType.STRING,
                    "required": True,
                },
            ],
        },
        "base32": {
            "name": "base32",
            "description": "Base32 encoding/decoding",
            "options": [
                {
                    "name": "mode",
                    "description": "Operation mode",
                    "option_type": OptionType.STRING,
                    "required": True,
                    "choices": ["encode", "decode"],
                },
                {
                    "name": "data",
                    "description": "The data to encode or decode",
                    "option_type": OptionType.STRING,
                    "required": True,
                },
            ],
        },
        "binary": {
            "name": "binary",
            "description": "Binary encoding/decoding",
            "options": [
                {
                    "name": "mode",
                    "description": "Operation mode",
                    "option_type": OptionType.STRING,
                    "required": True,
                    "choices": ["encode", "decode"],
                },
                {
                    "name": "data",
                    "description": "The data to encode or decode",
                    "option_type": OptionType.STRING,
                    "required": True,
                },
            ],
        },
        "hex": {
            "name": "hex",
            "description": "Hex encoding/decoding",
            "options": [
                {
                    "name": "mode",
                    "description": "Operation mode",
                    "option_type": OptionType.STRING,
                    "required": True,
                    "choices": ["encode", "decode"],
                },
                {
                    "name": "data",
                    "description": "The data to encode or decode",
                    "option_type": OptionType.STRING,
                    "required": True,
                },
            ],
        },
        "url": {
            "name": "url",
            "description": "URL encoding/decoding",
            "options": [
                {
                    "name": "mode",
                    "description": "Operation mode",
                    "option_type": OptionType.STRING,
                    "required": True,
                    "choices": ["encode", "decode"],
                },
                {
                    "name": "data",
                    "description": "The data to encode or decode",
                    "option_type": OptionType.STRING,
                    "required": True,
                },
            ],
        },
    },
}
