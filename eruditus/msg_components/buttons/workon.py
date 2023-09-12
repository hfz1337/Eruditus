import discord

from config import CHALLENGE_COLLECTION, DBNAME, MONGO
from lib.discord_util import add_challenge_solver, remove_challenge_solver


class WorkonButton(discord.ui.View):
    def __init__(self, name: str, disabled: bool = False) -> None:
        # Challenge name.
        self.name = name
        super().__init__(timeout=None)

        self.children[0].disabled = disabled
        self.children[0].label = (
            "Already solved." if disabled else "Work on this challenge!"
        )

    @discord.ui.button(style=discord.ButtonStyle.green)
    async def workon(
        self, interaction: discord.Interaction, _: discord.ui.Button
    ) -> None:
        challenge = MONGO[DBNAME][CHALLENGE_COLLECTION].find_one({"name": self.name})
        if interaction.user.name in challenge["players"]:
            await interaction.response.send_message(
                "You're already working on this challenge.", ephemeral=True
            )
            return

        challenge_thread = await add_challenge_solver(interaction, challenge)

        await interaction.response.send_message(
            f"✅ Added to the `{challenge['name']}` challenge.",
            view=UnworkonButton(name=self.name),
            ephemeral=True,
        )
        await challenge_thread.send(
            f"{interaction.user.mention} wants to collaborate 🤝"
        )


class UnworkonButton(discord.ui.View):
    def __init__(self, name: str) -> None:
        # Challenge name.
        self.name = name
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Stop working on this challenge.", style=discord.ButtonStyle.red
    )
    async def unworkon(
        self, interaction: discord.Interaction, _: discord.ui.Button
    ) -> None:
        challenge = MONGO[DBNAME][CHALLENGE_COLLECTION].find_one({"name": self.name})
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

        await remove_challenge_solver(interaction, challenge)
        await interaction.response.edit_message(
            content=f"✅ Removed from the `{challenge['name']}` challenge.", view=None
        )
