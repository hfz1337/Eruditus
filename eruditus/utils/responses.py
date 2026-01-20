"""Discord response pattern helpers for consistent command handling."""

from functools import wraps
from typing import Any, Callable, Coroutine, Optional, TypeVar

import discord
from constants import Emojis

T = TypeVar("T")


async def send_response(
    interaction: discord.Interaction,
    content: str,
    ephemeral: bool = True,
    **kwargs: Any,
) -> None:
    """Send a response, handling both deferred and non-deferred interactions.

    Args:
        interaction: The Discord interaction.
        content: The message content.
        ephemeral: Whether the message should be ephemeral.
        **kwargs: Additional arguments to pass to send_message/followup.send.
    """
    if interaction.response.is_done():
        await interaction.followup.send(content, ephemeral=ephemeral, **kwargs)
    else:
        await interaction.response.send_message(content, ephemeral=ephemeral, **kwargs)


async def send_error(
    interaction: discord.Interaction,
    message: str,
    ephemeral: bool = True,
) -> None:
    """Send an error message.

    Args:
        interaction: The Discord interaction.
        message: The error message.
        ephemeral: Whether the message should be ephemeral.
    """
    await send_response(interaction, f"{Emojis.ERROR} {message}", ephemeral=ephemeral)


async def send_success(
    interaction: discord.Interaction,
    message: str,
    ephemeral: bool = True,
) -> None:
    """Send a success message.

    Args:
        interaction: The Discord interaction.
        message: The success message.
        ephemeral: Whether the message should be ephemeral.
    """
    await send_response(interaction, f"{Emojis.SUCCESS} {message}", ephemeral=ephemeral)


async def send_warning(
    interaction: discord.Interaction,
    message: str,
    ephemeral: bool = True,
) -> None:
    """Send a warning message.

    Args:
        interaction: The Discord interaction.
        message: The warning message.
        ephemeral: Whether the message should be ephemeral.
    """
    await send_response(interaction, f"{Emojis.WARNING} {message}", ephemeral=ephemeral)


async def send_info(
    interaction: discord.Interaction,
    message: str,
    ephemeral: bool = True,
) -> None:
    """Send an info message.

    Args:
        interaction: The Discord interaction.
        message: The info message.
        ephemeral: Whether the message should be ephemeral.
    """
    await send_response(interaction, f"{Emojis.INFO} {message}", ephemeral=ephemeral)


def require_ctf_context(
    func: Callable[..., Coroutine[Any, Any, T]],
) -> Callable[..., Coroutine[Any, Any, Optional[T]]]:
    """Decorator that ensures a command is run within a CTF context.

    The decorated function must have 'interaction' as its first parameter
    after self, and the function's class must have '_ctf_repo' attribute.

    Args:
        func: The async function to decorate.

    Returns:
        The wrapped function that checks for CTF context.
    """

    @wraps(func)
    async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):
        ctf = self._ctf_repo.get_ctf_info(
            guild_category=interaction.channel.category_id
        )
        if ctf is None:
            await send_error(
                interaction, "This command can only be used from within a CTF channel."
            )
            return None
        # Inject ctf into kwargs for the decorated function
        kwargs["_ctf"] = ctf
        return await func(self, interaction, *args, **kwargs)

    return wrapper


def require_challenge_thread(
    func: Callable[..., Coroutine[Any, Any, T]],
) -> Callable[..., Coroutine[Any, Any, Optional[T]]]:
    """Decorator that ensures a command is run within a challenge thread.

    The decorated function must have 'interaction' as its first parameter
    after self, and the function's class must have '_challenge_repo' attribute.

    Args:
        func: The async function to decorate.

    Returns:
        The wrapped function that checks for challenge thread context.
    """

    @wraps(func)
    async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):
        challenge = self._challenge_repo.get_challenge_info(
            thread=interaction.channel_id
        )
        if challenge is None:
            await send_error(
                interaction,
                "This command can only be used from within a challenge thread.",
            )
            return None
        # Inject challenge into kwargs for the decorated function
        kwargs["_challenge"] = challenge
        return await func(self, interaction, *args, **kwargs)

    return wrapper


class CTFContextMixin:
    """Mixin providing CTF context helper methods."""

    _ctf_repo: Any  # CTFRepository

    def get_ctf_from_context(self, interaction: discord.Interaction) -> Optional[dict]:
        """Get CTF from the current channel context.

        Args:
            interaction: The Discord interaction.

        Returns:
            The CTF document or None if not in a CTF channel.
        """
        return self._ctf_repo.get_ctf_info(
            guild_category=interaction.channel.category_id
        )

    async def get_ctf_channel(
        self,
        guild: discord.Guild,
        ctf: dict,
        channel_name: str,
    ) -> Optional[discord.TextChannel]:
        """Get a specific CTF channel.

        Args:
            guild: The Discord guild.
            ctf: The CTF document.
            channel_name: The channel type (e.g., 'scoreboard', 'solves').

        Returns:
            The text channel or None if not found.
        """
        channel_id = ctf.get("guild_channels", {}).get(channel_name)
        if channel_id:
            return discord.utils.get(guild.text_channels, id=channel_id)
        return None
