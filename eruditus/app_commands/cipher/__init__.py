from string import ascii_lowercase, ascii_uppercase
from typing import Optional

from discord import Interaction, app_commands


class ClassicCiphers:
    """Implementation of some basic classic ciphers."""

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


class Cipher(app_commands.Group):
    """Encryption/Decryption using classic ciphers."""

    @app_commands.command()
    async def caesar(
        self, interaction: Interaction, message: str, key: Optional[int]
    ) -> None:
        """Caesar cipher

        Args:
            interaction: The interaction that triggered this command.
            message: The message encrypt/decrypt.
            key: The key to be used for encryption/decryption (default: brute force).
        """
        if key is None:
            result = "\n".join(
                f"{key:>2} | {ClassicCiphers.caesar(message, key)}"
                for key in range(1, 26)
            )
        else:
            result = ClassicCiphers.caesar(message, int(key))

        await interaction.response.send_message(f"```\n{result}\n```")

    @app_commands.command()
    async def rot13(self, interaction: Interaction, message: str) -> None:
        """Rot13 cipher

        Args:
            interaction: The interaction that triggered this command.
            message: The message encrypt/decrypt.
        """
        await interaction.response.send_message(
            f"```\n{ClassicCiphers.rot13(message)}\n```"
        )

    @app_commands.command()
    async def atbash(self, interaction: Interaction, message: str) -> None:
        """Atbash cipher

        Args:
            interaction: The interaction that triggered this command.
            message: The message encrypt/decrypt.
        """
        await interaction.response.send_message(
            f"```\n{ClassicCiphers.atbash(message)}\n```"
        )
