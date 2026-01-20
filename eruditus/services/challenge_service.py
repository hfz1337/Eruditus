"""Service for challenge-related business logic."""

import re
from typing import Optional

import discord
from constants import DEFAULT_AUTO_ARCHIVE_DURATION, CategoryPrefixes, Emojis
from db.challenge_repository import ChallengeRepository
from utils.formatting import sanitize_channel_name


class ChallengeService:
    """Service for managing CTF challenges."""

    def __init__(self) -> None:
        """Initialize the challenge service."""
        self._repo = ChallengeRepository()

    async def get_or_create_category_channel(
        self,
        guild: discord.Guild,
        ctf_category_channel: discord.CategoryChannel,
        category: str,
    ) -> discord.TextChannel:
        """Get or create a text channel for a challenge category.

        Args:
            guild: The Discord guild object.
            ctf_category_channel: The CTF category channel.
            category: The challenge category name.

        Returns:
            The text channel associated to the CTF category.
        """
        channel_name = sanitize_channel_name(category)

        for prefix in CategoryPrefixes.ALL:
            if text_channel := discord.utils.get(
                guild.text_channels,
                category=ctf_category_channel,
                name=f"{prefix}-{channel_name}",
            ):
                return text_channel

        return await guild.create_text_channel(
            name=f"{Emojis.ACTIVE}-{channel_name}",
            category=ctf_category_channel,
            default_auto_archive_duration=DEFAULT_AUTO_ARCHIVE_DURATION,
        )

    async def mark_category_if_completed(
        self, text_channel: discord.TextChannel, category: str
    ) -> None:
        """Mark a category channel as completed if all challenges are solved.

        Args:
            text_channel: The text channel associated to the CTF category.
            category: The CTF category name.
        """
        challenges = self._repo.find_by_category(category)
        if any(not c["solved"] for c in challenges):
            return

        if text_channel.name.startswith(Emojis.ACTIVE):
            await text_channel.edit(
                name=text_channel.name.replace(Emojis.ACTIVE, Emojis.MAXED)
            )

    async def add_worker(
        self,
        challenge_thread: discord.Thread,
        challenge: dict,
        member: discord.Member,
    ) -> None:
        """Add a member to a challenge's worker list.

        Args:
            challenge_thread: The thread associated to the challenge.
            challenge: The challenge document.
            member: The member to add.
        """
        if member.name not in challenge["players"]:
            challenge["players"].append(member.name)
            self._repo.set_players(challenge["_id"], challenge["players"])
        await challenge_thread.add_user(member)

    async def remove_worker(
        self,
        challenge_thread: discord.Thread,
        challenge: dict,
        member: discord.Member,
    ) -> None:
        """Remove a member from a challenge's worker list.

        Args:
            challenge_thread: The thread associated to the challenge.
            challenge: The challenge document.
            member: The member to remove.
        """
        if member.name in challenge["players"]:
            challenge["players"].remove(member.name)
            self._repo.set_players(challenge["_id"], challenge["players"])
        await challenge_thread.remove_user(member)

    async def parse_solvers(
        self,
        interaction: discord.Interaction,
        challenge: dict,
        members: Optional[str] = None,
    ) -> list[str]:
        """Return a list of users who contributed in solving a challenge.

        Args:
            interaction: The Discord interaction.
            challenge: The challenge document.
            members: A string containing member mentions of those who contributed.

        Returns:
            A list of user names.
        """
        if interaction.user.name not in challenge["players"]:
            challenge["players"].append(interaction.user.name)

        additional_members = set()
        if members:
            parsed = await self.parse_member_mentions(interaction, members)
            additional_members = {m.name for m in parsed}

        return list({interaction.user.name} | additional_members)

    async def parse_member_mentions(
        self, interaction: discord.Interaction, members: str
    ) -> list[discord.Member]:
        """Extract Discord members mentioned in a string.

        Args:
            interaction: The Discord interaction.
            members: A string containing member mentions.

        Returns:
            A list of Discord member objects.
        """
        result = []
        for member_id in re.findall(r"<@!?([0-9]{15,20})>", members):
            member = await interaction.guild.fetch_member(int(member_id))
            if member:
                result.append(member)
        return result
