#
# Eruditus - Encoding cog
#
# ======================================================================================
# Implements some basic encoding/decoding functionalities.
# - Base64
# - Base32
# - Binary
# - Hex
# - URL
# ======================================================================================

from base64 import b64encode, b64decode, b32encode, b32decode
from discord.ext.commands import Context, Bot
from binascii import hexlify, unhexlify
from discord.ext import commands
from help import help_info
import urllib.parse
import discord


class Encoding(commands.Cog):
    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    @commands.group()
    async def encoding(self, ctx: Context) -> None:
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

    @encoding.command()
    async def base64(self, ctx: Context, mode: str, string: str) -> None:
        if mode == "encode":
            data = b64encode(string.encode()).decode()
        else:
            data = b64decode(string)
            try:
                data = data.decode()
            except UnicodeDecodeError:
                data = str(data)

        await ctx.send(f"```\n{data}\n```")

    @encoding.command()
    async def base32(self, ctx: Context, mode: str, string: str) -> None:
        if mode == "encode":
            data = b32encode(string.encode()).decode()
        else:
            data = b32decode(string)
            try:
                data = data.decode()
            except UnicodeDecodeError:
                data = str(data)

        await ctx.send(f"```\n{data}\n```")

    @encoding.command()
    async def binary(self, ctx: Context, mode: str, string: str) -> None:
        if mode == "encode":
            data = bin(int.from_bytes(string.encode(), "big"))[2:]
            data = "0" * (8 - len(data) % 8) + data
        else:
            data = int(string.strip().replace(" ", ""), 2)
            data = data.to_bytes(data.bit_length() // 8 + 1, "big")
            try:
                data = data.decode()
            except UnicodeDecodeError:
                data = str(data)

        await ctx.send(f"```\n{data}\n```")

    @encoding.command()
    async def hex(self, ctx: Context, mode: str, string: str) -> None:
        if mode == "encode":
            data = hexlify(string.encode()).decode()
        else:
            data = unhexlify(string.strip().replace(" ", ""))
            try:
                data = data.decode()
            except UnicodeDecodeError:
                data = str(data)

        await ctx.send(f"```\n{data}\n```")

    @encoding.command()
    async def url(self, ctx: Context, mode: str, string: str) -> None:
        if mode == "encode":
            data = urllib.parse.quote(string)
        else:
            data = urllib.parse.unquote(string)

        await ctx.send(f"```\n{data}\n```")


def setup(bot: Bot) -> None:
    bot.add_cog(Encoding(bot))
