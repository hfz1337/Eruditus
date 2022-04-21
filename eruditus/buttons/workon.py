import discord

from config import MONGO, DBNAME, CHALLENGE_COLLECTION


class WorkonButton(discord.ui.View):
    def __init__(self, name: str):
        # Challenge name.
        self.name = name
        super().__init__(timeout=None)

    @discord.ui.button(label="Work on this challenge!", style=discord.ButtonStyle.green)
    async def workon(self, interaction: discord.Interaction, button: discord.ui.Button):
        challenge = MONGO[DBNAME][CHALLENGE_COLLECTION].find_one({"name": self.name})
        if challenge is None:
            await interaction.response.send_message(
                "No such challenge.", ephemeral=True
            )
            return

        if interaction.user.name in challenge["players"]:
            await interaction.response.send_message(
                "You're already working on this challenge.", ephemeral=True
            )
            return

        if challenge["solved"]:
            await interaction.response.send_message(
                "You can't work on a challenge that has been solved.", ephemeral=True
            )
            return

        challenge["players"].append(interaction.user.name)

        challenge_channel = discord.utils.get(
            interaction.guild.text_channels, id=challenge["channel"]
        )

        await challenge_channel.set_permissions(interaction.user, read_messages=True)

        MONGO[DBNAME][CHALLENGE_COLLECTION].update_one(
            {"_id": challenge["_id"]},
            {"$set": {"players": challenge["players"]}},
        )

        await interaction.response.send_message(
            (f"✅ Added to the `{challenge['name']}` challenge."),
            view=UnworkonButton(name=self.name),
            ephemeral=True,
        )
        await challenge_channel.send(
            f"{interaction.user.mention} wants to collaborate 🤝"
        )


class UnworkonButton(discord.ui.View):
    def __init__(self, name: str):
        # Challenge name.
        self.name = name
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Stop working on this challenge.", style=discord.ButtonStyle.red
    )
    async def unworkon(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
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

        challenge_channel = discord.utils.get(
            interaction.guild.text_channels, id=challenge["channel"]
        )

        MONGO[DBNAME][CHALLENGE_COLLECTION].update_one(
            {"_id": challenge["_id"]},
            {"$set": {"players": challenge["players"]}},
        )

        await interaction.response.edit_message(
            content=f"✅ Removed from the `{challenge['name']}` challenge.", view=None
        )
        await challenge_channel.send(
            f"{interaction.user.mention} left you alone, what a chicken! 🐥"
        )

        await challenge_channel.set_permissions(interaction.user, overwrite=None)
