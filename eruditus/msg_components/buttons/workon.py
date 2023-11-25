import discord
from bson import ObjectId

from lib.discord_util import add_challenge_worker, remove_challenge_worker
from lib.util import get_challenge_info


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
        challenge = get_challenge_info(_id=self.oid)
        if interaction.user.name in challenge["players"]:
            await interaction.response.send_message(
                "You're already working on this challenge.", ephemeral=True
            )
            return

        challenge_thread = discord.utils.get(
            interaction.guild.threads, id=challenge["thread"]
        )
        await add_challenge_worker(challenge_thread, challenge, interaction.user)

        await interaction.response.send_message(
            f"✅ Added to the `{challenge['name']}` challenge.",
            view=UnworkonButton(oid=self.oid),
            ephemeral=True,
        )
        await challenge_thread.send(
            f"{interaction.user.mention} wants to collaborate 🤝"
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
        challenge = get_challenge_info(_id=self.oid)
        if challenge is None:
            await interaction.response.edit_message(
                content="No such challenge.", view=None
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
            f"{interaction.user.name} left you alone, what a chicken! 🐥"
        )

        await interaction.response.edit_message(
            content=f"✅ Removed from the `{challenge['name']}` challenge.",
            view=None,
        )


class UnworkonButton(discord.ui.View):
    def __init__(self, oid: ObjectId) -> None:
        super().__init__(timeout=None)
        self.add_item(_UnworkonButton(oid=oid))
