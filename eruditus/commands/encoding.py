import binascii
from base64 import b32decode, b32encode, b64decode, b64encode
from binascii import hexlify, unhexlify
from urllib.parse import quote, unquote

import discord
from discord import app_commands
from models.enums import EncodingOperationMode
from utils.responses import send_response


class Encoding(app_commands.Group):
    """Simple encoding/decoding utility."""

    @app_commands.command()
    async def base64(
        self, interaction: discord.Interaction, mode: EncodingOperationMode, data: str
    ) -> None:
        """Base64 encoding/decoding.

        Args:
            interaction: Discord interaction.
            mode: Operation mode.
            data: The data to encode or decode.
        """
        if mode.value == 1:
            data = b64encode(data.encode()).decode()
        else:
            try:
                data = b64decode(data)
            except binascii.Error:
                await send_response(interaction, "Invalid input.")
                return

            try:
                data = data.decode()
            except UnicodeDecodeError:
                data = str(data)

        await send_response(interaction, f"```\n{data}\n```", ephemeral=False)

    @app_commands.command()
    async def base32(
        self, interaction: discord.Interaction, mode: EncodingOperationMode, data: str
    ) -> None:
        """Base32 encoding/decoding.

        Args:
            interaction: Discord interaction.
            mode: Operation mode.
            data: The data to encode or decode.
        """
        if mode.value == 1:
            data = b32encode(data.encode()).decode()
        else:
            try:
                data = b32decode(data)
            except binascii.Error:
                await send_response(interaction, "Invalid input.")
                return

            try:
                data = data.decode()
            except UnicodeDecodeError:
                data = str(data)

        await send_response(interaction, f"```\n{data}\n```", ephemeral=False)

    @app_commands.command()
    async def binary(
        self, interaction: discord.Interaction, mode: EncodingOperationMode, data: str
    ) -> None:
        """Binary encoding/decoding.

        Args:
            interaction: Discord interaction.
            mode: Operation mode.
            data: The data to encode or decode.
        """
        if mode.value == 1:
            data = bin(int.from_bytes(data.encode(), "big"))[2:]
            data = "0" * (8 - len(data) % 8) + data
        else:
            data = data.strip().replace(" ", "")
            if all(digit in {"0", "1"} for digit in data):
                data = int(data, 2)
                data = data.to_bytes(data.bit_length() // 8 + 1, "big")
                try:
                    data = data.decode()
                except UnicodeDecodeError:
                    data = str(data)
            else:
                await send_response(interaction, "Error: non-binary digits found.")
                return

        await send_response(interaction, f"```\n{data}\n```", ephemeral=False)

    @app_commands.command()
    async def hex(
        self, interaction: discord.Interaction, mode: EncodingOperationMode, data: str
    ) -> None:
        """Hex encoding/decoding.

        Args:
            interaction: Discord interaction.
            mode: Operation mode.
            data: The data to encode or decode.
        """
        if mode.value == 1:
            data = hexlify(data.encode()).decode()
        else:
            data = data.strip().replace(" ", "")
            try:
                data = unhexlify(data)
                data = data.decode()
            except binascii.Error as error:
                await send_response(interaction, f"Error: {error}")
                return
            except UnicodeDecodeError:
                data = str(data)

        await send_response(interaction, f"```\n{data}\n```", ephemeral=False)

    @app_commands.command()
    async def url(
        self, interaction: discord.Interaction, mode: EncodingOperationMode, data: str
    ) -> None:
        """URL encoding/decoding.

        Args:
            interaction: Discord interaction.
            mode: Operation mode.
            data: The data to encode or decode.
        """
        if mode.value == 1:
            data = quote(data)
        else:
            data = unquote(data)

        await send_response(interaction, f"```\n{data}\n```", ephemeral=False)
