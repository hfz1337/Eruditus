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
from binascii import hexlify, unhexlify
import urllib.parse

from discord.ext import commands
from discord.ext.commands import Bot

from discord_slash import SlashContext, cog_ext
from discord_slash.utils.manage_commands import create_option

from cogs.encoding.help import cog_help


class Encoding(commands.Cog):
    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    @cog_ext.cog_subcommand(
        base=cog_help["name"],
        name=cog_help["subcommands"]["base64"]["name"],
        description=cog_help["subcommands"]["base64"]["description"],
        options=[
            create_option(**option)
            for option in cog_help["subcommands"]["base64"]["options"]
        ],
    )
    async def _base64(self, ctx: SlashContext, mode: str, data: str) -> None:
        if mode == "encode":
            data = b64encode(data.encode()).decode()
        else:
            data = b64decode(data)
            try:
                data = data.decode()
            except UnicodeDecodeError:
                data = str(data)

        await ctx.send(f"```\n{data}\n```")

    @cog_ext.cog_subcommand(
        base=cog_help["name"],
        name=cog_help["subcommands"]["base32"]["name"],
        description=cog_help["subcommands"]["base32"]["description"],
        options=[
            create_option(**option)
            for option in cog_help["subcommands"]["base32"]["options"]
        ],
    )
    async def _base32(self, ctx: SlashContext, mode: str, data: str) -> None:
        if mode == "encode":
            data = b32encode(data.encode()).decode()
        else:
            data = b32decode(data)
            try:
                data = data.decode()
            except UnicodeDecodeError:
                data = str(data)

        await ctx.send(f"```\n{data}\n```")

    @cog_ext.cog_subcommand(
        base=cog_help["name"],
        name=cog_help["subcommands"]["binary"]["name"],
        description=cog_help["subcommands"]["binary"]["description"],
        options=[
            create_option(**option)
            for option in cog_help["subcommands"]["binary"]["options"]
        ],
    )
    async def _binary(self, ctx: SlashContext, mode: str, data: str) -> None:
        if mode == "encode":
            data = bin(int.from_bytes(data.encode(), "big"))[2:]
            data = "0" * (8 - len(data) % 8) + data
        else:
            data = int(data.strip().replace(" ", ""), 2)
            data = data.to_bytes(data.bit_length() // 8 + 1, "big")
            try:
                data = data.decode()
            except UnicodeDecodeError:
                data = str(data)

        await ctx.send(f"```\n{data}\n```")

    @cog_ext.cog_subcommand(
        base=cog_help["name"],
        name=cog_help["subcommands"]["hex"]["name"],
        description=cog_help["subcommands"]["hex"]["description"],
        options=[
            create_option(**option)
            for option in cog_help["subcommands"]["hex"]["options"]
        ],
    )
    async def _hex(self, ctx: SlashContext, mode: str, data: str) -> None:
        if mode == "encode":
            data = hexlify(data.encode()).decode()
        else:
            data = unhexlify(data.strip().replace(" ", ""))
            try:
                data = data.decode()
            except UnicodeDecodeError:
                data = str(data)

        await ctx.send(f"```\n{data}\n```")

    @cog_ext.cog_subcommand(
        base=cog_help["name"],
        name=cog_help["subcommands"]["url"]["name"],
        description=cog_help["subcommands"]["url"]["description"],
        options=[
            create_option(**option)
            for option in cog_help["subcommands"]["url"]["options"]
        ],
    )
    async def _url(self, ctx: SlashContext, mode: str, data: str) -> None:
        if mode == "encode":
            data = urllib.parse.quote(data)
        else:
            data = urllib.parse.unquote(data)

        await ctx.send(f"```\n{data}\n```")


def setup(bot: Bot) -> None:
    bot.add_cog(Encoding(bot))
