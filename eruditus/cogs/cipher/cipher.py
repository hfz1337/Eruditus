#
# Eruditus - Cipher cog
#
# ======================================================================================
# Implements some classic cipher functionalities.
# - Caesar
# - Rot13
# - Atbash
# ======================================================================================

from string import ascii_lowercase, ascii_uppercase

from discord.ext import commands
from discord.ext.commands import Bot

from discord_slash import SlashContext, cog_ext
from discord_slash.utils.manage_commands import create_option

from cogs.cipher.help import cog_help


class ClassicCiphers:
    @staticmethod
    def caesar(message: str, key: int) -> str:
        return "".join(
            chr((ord(i) - (97, 65)[i.isupper()] + key) % 26 + (97, 65)[i.isupper()])
            if i.isalpha()
            else i
            for i in message
        )

    @staticmethod
    def rot13(message: str) -> str:
        return ClassicCiphers.caesar(message, 13)

    @staticmethod
    def atbash(message: str) -> str:
        return message.translate(
            {
                **str.maketrans(ascii_lowercase, ascii_lowercase[::-1]),
                **str.maketrans(ascii_uppercase, ascii_uppercase[::-1]),
            }
        )


class Cipher(commands.Cog):
    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    @cog_ext.cog_subcommand(
        base=cog_help["name"],
        name=cog_help["subcommands"]["caesar"]["name"],
        description=cog_help["subcommands"]["caesar"]["description"],
        options=[
            create_option(**option)
            for option in cog_help["subcommands"]["caesar"]["options"]
        ],
    )
    async def _caesar(self, ctx: SlashContext, message: str, key: int = None) -> None:
        if key is None:
            result = "\n".join(
                f"{key:>2} | {ClassicCiphers.caesar(message, key)}"
                for key in range(1, 26)
            )
        else:
            result = ClassicCiphers.caesar(message, int(key))

        await ctx.send(f"```\n{result}\n```")

    @cog_ext.cog_subcommand(
        base=cog_help["name"],
        name=cog_help["subcommands"]["rot13"]["name"],
        description=cog_help["subcommands"]["rot13"]["description"],
        options=[
            create_option(**option)
            for option in cog_help["subcommands"]["rot13"]["options"]
        ],
    )
    async def _rot13(self, ctx: SlashContext, message: str) -> None:
        await ctx.send(f"```\n{ClassicCiphers.rot13(message)}\n```")

    @cog_ext.cog_subcommand(
        base=cog_help["name"],
        name=cog_help["subcommands"]["atbash"]["name"],
        description=cog_help["subcommands"]["atbash"]["description"],
        options=[
            create_option(**option)
            for option in cog_help["subcommands"]["atbash"]["options"]
        ],
    )
    async def _atbash(self, ctx: SlashContext, message: str) -> None:
        await ctx.send(f"```\n{ClassicCiphers.atbash(message)}\n```")


def setup(bot: Bot) -> None:
    bot.add_cog(Cipher(bot))
