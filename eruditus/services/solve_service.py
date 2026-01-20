"""Service for challenge solve-related business logic."""

import logging
from datetime import datetime
from typing import Optional

import discord
from components.buttons.workon import WorkonButton
from constants import EmbedColours, Emojis, ThreadPrefixes
from db.challenge_repository import ChallengeRepository
from utils.discord import mark_if_maxed

_log = logging.getLogger(__name__)


class SolveService:
    """Service for managing challenge solves."""

    def __init__(self) -> None:
        """Initialize the solve service."""
        self._challenge_repo = ChallengeRepository()

    def create_solve_embed(
        self,
        solvers: list[str],
        challenge_name: str,
        category: str,
        is_first_blood: bool,
        user_avatar_url: str,
    ) -> discord.Embed:
        """Create an embed for a solve announcement.

        Args:
            solvers: List of solver names.
            challenge_name: Name of the challenge.
            category: Challenge category.
            is_first_blood: Whether this is a first blood.
            user_avatar_url: URL of the user's avatar.

        Returns:
            Discord embed for the announcement.
        """
        solver_names = ", ".join(solvers)

        if is_first_blood:
            return discord.Embed(
                title=f"{Emojis.FIRST_BLOOD} First blood!",
                description=(
                    f"**{solver_names}** just blooded "
                    f"**{challenge_name}** from the "
                    f"**{category}** category!"
                ),
                colour=EmbedColours.FIRST_BLOOD,
                timestamp=datetime.now(),
            ).set_thumbnail(url=user_avatar_url)
        else:
            return discord.Embed(
                title=f"{Emojis.CELEBRATION} Challenge solved!",
                description=(
                    f"**{solver_names}** just solved "
                    f"**{challenge_name}** from the "
                    f"**{category}** category!"
                ),
                colour=EmbedColours.SUCCESS,
                timestamp=datetime.now(),
            ).set_thumbnail(url=user_avatar_url)

    async def announce_solve(
        self,
        guild: discord.Guild,
        ctf: dict,
        challenge: dict,
        solvers: list[str],
        is_first_blood: bool,
        user_avatar_url: str,
        flag: Optional[str] = None,
    ) -> int:
        """Announce a challenge solve and update all related state.

        Args:
            guild: The Discord guild.
            ctf: The CTF document.
            challenge: The challenge document.
            solvers: List of solver names.
            is_first_blood: Whether this is a first blood.
            user_avatar_url: URL of the user's avatar.
            flag: The submitted flag (optional).

        Returns:
            The announcement message ID.
        """
        # Create and send the announcement
        embed = self.create_solve_embed(
            solvers=solvers,
            challenge_name=challenge["name"],
            category=challenge["category"],
            is_first_blood=is_first_blood,
            user_avatar_url=user_avatar_url,
        )

        solves_channel = guild.get_channel(ctf["guild_channels"]["solves"])
        announcement = await solves_channel.send(embed=embed)

        # Update challenge in database
        solve_time = int(datetime.now().timestamp())
        self._challenge_repo.update_solve_details(
            challenge_id=challenge["_id"],
            solved=True,
            blooded=is_first_blood,
            solve_time=solve_time,
            solve_announcement=announcement.id,
            players=solvers if solvers else challenge.get("players", []),
            flag=flag,
        )

        # Disable workon button
        announcements_channel = discord.utils.get(
            guild.text_channels,
            id=ctf["guild_channels"]["announcements"],
        )
        if announcements_channel and challenge.get("announcement"):
            try:
                challenge_announcement = await announcements_channel.fetch_message(
                    challenge["announcement"]
                )
                await challenge_announcement.edit(
                    view=WorkonButton(oid=challenge["_id"], disabled=True)
                )
            except discord.NotFound:
                _log.debug(
                    "Challenge announcement message not found, skipping button update"
                )

        return announcement.id

    async def update_thread_status(
        self,
        thread: discord.Thread,
        is_solved: bool,
        is_first_blood: bool = False,
    ) -> None:
        """Update a challenge thread's name to reflect its status.

        Args:
            thread: The challenge thread.
            is_solved: Whether the challenge is solved.
            is_first_blood: Whether it was a first blood.
        """
        current_name = thread.name
        new_prefix = ThreadPrefixes.get_prefix(is_solved, is_first_blood)

        # Remove existing prefix and add new one
        for old_prefix in (
            ThreadPrefixes.UNSOLVED,
            ThreadPrefixes.SOLVED,
            ThreadPrefixes.FIRST_BLOOD,
        ):
            if current_name.startswith(old_prefix):
                new_name = new_prefix + current_name[len(old_prefix) :]
                break
        else:
            new_name = current_name

        if new_name != current_name:
            await thread.edit(name=new_name)

    async def process_solve(
        self,
        interaction: discord.Interaction,
        ctf: dict,
        challenge: dict,
        solvers: list[str],
        is_first_blood: bool,
        flag: Optional[str] = None,
    ) -> None:
        """Process a complete solve flow including announcement and thread update.

        Args:
            interaction: The Discord interaction.
            ctf: The CTF document.
            challenge: The challenge document.
            solvers: List of solver names.
            is_first_blood: Whether this is a first blood.
            flag: The submitted flag (optional).
        """
        # Send announcement
        await self.announce_solve(
            guild=interaction.guild,
            ctf=ctf,
            challenge=challenge,
            solvers=solvers,
            is_first_blood=is_first_blood,
            user_avatar_url=interaction.user.display_avatar.url,
            flag=flag,
        )

        # Update thread status
        challenge_thread = discord.utils.get(
            interaction.guild.threads, id=challenge["thread"]
        )
        if challenge_thread:
            await self.update_thread_status(
                thread=challenge_thread,
                is_solved=True,
                is_first_blood=is_first_blood,
            )

        # Mark category as maxed if all challenges solved
        if interaction.channel and interaction.channel.parent:
            await mark_if_maxed(interaction.channel.parent, challenge["category"])
