import discord

from config import CHALLENGE_COLLECTION, DBNAME, MONGO


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

        challenge["players"].append(interaction.user.name)

        challenge_thread = discord.utils.get(
            interaction.guild.threads, id=challenge["thread"]
        )

        await challenge_thread.add_user(interaction.user)

        MONGO[DBNAME][CHALLENGE_COLLECTION].update_one(
            {"_id": challenge["_id"]},
            {"$set": {"players": challenge["players"]}},
        )

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

        challenge["players"].remove(interaction.user.name)

        challenge_thread = discord.utils.get(
            interaction.guild.threads, id=challenge["thread"]
        )

        MONGO[DBNAME][CHALLENGE_COLLECTION].update_one(
            {"_id": challenge["_id"]},
            {"$set": {"players": challenge["players"]}},
        )

        await interaction.response.edit_message(
            content=f"✅ Removed from the `{challenge['name']}` challenge.", view=None
        )
        await challenge_thread.send(
            f"{interaction.user.mention} left you alone, what a chicken! 🐥"
        )

        await challenge_thread.remove_user(interaction.user)
