from discord_slash.model import SlashCommandOptionType as OptionType

cog_help = {
    "name": "syscalls",
    "description": "Show information about a syscall from a specific architecture",
    "options": [
        {
            "name": "arch",
            "description": "Architecture",
            "option_type": OptionType.STRING,
            "required": True,
            "choices": ["x86", "x64", "arm", "armthumb"],
        },
        {
            "name": "syscall",
            "description": "Syscall name or ID (decimal and hex are supported)",
            "option_type": OptionType.STRING,
            "required": True,
        },
    ],
}
