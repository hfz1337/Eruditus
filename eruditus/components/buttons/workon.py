import discord
from bson import ObjectId
from constants import Emojis, ErrorMessages
from db.challenge_repository import ChallengeRepository
from utils.discord import add_challenge_worker, remove_challenge_worker
from utils.responses import send_response

_challenge_repo = ChallengeRepository()


class _WorkonButton(discord.ui.Button):
    def __init__(self, oid: ObjectId, disabled: bool = False) -> None:
        super().__init__(
            style=discord.ButtonStyle.green,
            custom_id=f"workon::{oid}",  # make button persistent across restarts
            disabled=disabled,
            label="Already solved." if disabled else "Work on this challenge!",
        )
        self.oid = oid

    async def callback(self, interaction: discord.Interaction) -> None:
        challenge = _challenge_repo.get_challenge_info(_id=self.oid)
        if interaction.user.name in challenge["players"]:
            await send_response(
                interaction, "You're already working on this challenge."
            )
            return

        challenge_thread = discord.utils.get(
            interaction.guild.threads, id=challenge["thread"]
        )
        await add_challenge_worker(challenge_thread, challenge, interaction.user)

        await interaction.response.send_message(
            f"{Emojis.SUCCESS} Added to the `{challenge['name']}` challenge.",
            view=UnworkonButton(oid=self.oid),
            ephemeral=True,
        )
        await challenge_thread.send(
            f"{interaction.user.mention} wants to collaborate {Emojis.HANDSHAKE}"
        )


class WorkonButton(discord.ui.View):
    def __init__(self, oid: ObjectId, disabled: bool = False) -> None:
        super().__init__(timeout=None)
        self.add_item(_WorkonButton(oid=oid, disabled=disabled))


class _UnworkonButton(discord.ui.Button):
    def __init__(self, oid: ObjectId) -> None:
        super().__init__(
            style=discord.ButtonStyle.red,
            label="Stop working on this challenge.",
        )
        self.oid = oid

    async def callback(self, interaction: discord.Interaction) -> None:
        challenge = _challenge_repo.get_challenge_info(_id=self.oid)
        if challenge is None:
            await interaction.response.edit_message(
                content=ErrorMessages.CHALLENGE_NOT_FOUND, view=None
            )
            return

        if interaction.user.name not in challenge["players"]:
            await interaction.response.edit_message(
                content="You're not working on this challenge in the first place.",
                view=None,
            )
            return

        challenge_thread = discord.utils.get(
            interaction.guild.threads, id=challenge["thread"]
        )
        await remove_challenge_worker(challenge_thread, challenge, interaction.user)
        await challenge_thread.send(
            f"{interaction.user.name} left you alone, what a chicken! {Emojis.CHICKEN}"
        )

        await interaction.response.edit_message(
            content=f"{Emojis.SUCCESS} Removed from `{challenge['name']}`.",
            view=None,
        )


class UnworkonButton(discord.ui.View):
    def __init__(self, oid: ObjectId) -> None:
        super().__init__(timeout=None)
        self.add_item(_UnworkonButton(oid=oid))
