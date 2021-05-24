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
from discord.ext.commands import Bot, Context
from discord.ext import commands
from help import help_info
import discord


class ClassicCiphers:
    @staticmethod
    def caesar(message: str, key: int) -> str:
        y = lambda x: 65 if x.isupper() else 97
        return "".join(
            chr((ord(i) - y(i) + key) % 26 + y(i)) if i.isalpha() else i
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

    @commands.group()
    async def cipher(self, ctx: Context) -> None:
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(
                title=f"Commands group for {self.bot.command_prefix}{ctx.invoked_with}",
                colour=discord.Colour.blue(),
            ).set_thumbnail(url=f"{self.bot.user.avatar_url}")

            for command in help_info[ctx.invoked_with]:
                embed.add_field(
                    name=help_info[ctx.invoked_with][command]["usage"].format(
                        self.bot.command_prefix
                    ),
                    value=help_info[ctx.invoked_with][command]["brief"],
                    inline=False,
                )

            await ctx.send(embed=embed)

    @cipher.command()
    async def caesar(self, ctx: Context, message: str, key: int = None) -> None:
        if key is None:
            result = "\n".join(
                f"{key:>2} | {ClassicCiphers.caesar(message, key)}"
                for key in range(1, 26)
            )
        else:
            result = ClassicCiphers.caesar(message, int(key))

        await ctx.send(f"```\n{result}\n```")

    @cipher.command()
    async def rot13(self, ctx: Context, message: str) -> None:
        await ctx.send(f"```\n{ClassicCiphers.rot13(message)}\n```")

    @cipher.command()
    async def atbash(self, ctx: Context, message: str) -> None:
        await ctx.send(f"```\n{ClassicCiphers.atbash(message)}\n```")


def setup(bot: Bot) -> None:
    bot.add_cog(Cipher(bot))
