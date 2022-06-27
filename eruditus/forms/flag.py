import discord
from discord import HTTPException

from datetime import datetime

from lib.ctfd import submit_flag
from buttons.workon import WorkonButton
from config import (
    CHALLENGE_COLLECTION,
    CTF_COLLECTION,
    DBNAME,
    MONGO,
)


class FlagSubmissionForm(discord.ui.Modal, title="Flag submission form"):
    flag = discord.ui.TextInput(
        label="Flag",
        placeholder=r"ctf{s0m3th1ng_l33t}",
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()

        challenge = MONGO[f"{DBNAME}"][CHALLENGE_COLLECTION].find_one(
            {"channel": interaction.channel_id}
        )
        if challenge is None:
            await interaction.followup.send(
                "❌ This command may only be used from within a challenge channel.",
                ephemeral=True,
            )
            return

        ctf = MONGO[f"{DBNAME}"][CTF_COLLECTION].find_one(
            {"guild_category": interaction.channel.category_id}
        )
        ctfd_url = ctf["credentials"]["url"]
        username = ctf["credentials"]["username"]
        password = ctf["credentials"]["password"]

        status, first_blood = await submit_flag(
            ctfd_url, username, password, challenge["id"], self.flag.value
        )
        if status is None:
            await interaction.followup.send(
                "❌ Failed to submit the flag.", ephemeral=True
            )
        elif status == "correct":
            # Announce that the challenge was solved.
            challenge["solved"] = True
            challenge["solve_time"] = int(datetime.now().timestamp())

            solves_channel = interaction.client.get_channel(
                ctf["guild_channels"]["solves"]
            )

            # Add the user who triggered this interaction to the list of players, useful
            # in case the one who triggered the interaction is an admin.
            if interaction.user.name not in challenge["players"]:
                challenge["players"].append(interaction.user.name)

            if first_blood:
                challenge["blooded"] = True
                await interaction.followup.send("🩸 Well done, you got first blood!")
                embed = discord.Embed(
                    title="🩸 First blood!",
                    description=(
                        f"**{', '.join(challenge['players'])}** just blooded "
                        f"**{challenge['name']}** from the "
                        f"**{challenge['category']}** category!"
                    ),
                    colour=discord.Colour.red(),
                    timestamp=datetime.now(),
                ).set_thumbnail(url=interaction.user.display_avatar.url)
            else:
                await interaction.followup.send("✅ Well done, challenge solved!")
                embed = discord.Embed(
                    title="🎉 Challenge solved!",
                    description=(
                        f"**{', '.join(challenge['players'])}** just solved "
                        f"**{challenge['name']}** from the "
                        f"**{challenge['category']}** category!"
                    ),
                    colour=discord.Colour.dark_gold(),
                    timestamp=datetime.now(),
                ).set_thumbnail(url=interaction.user.display_avatar.url)
            announcement = await solves_channel.send(embed=embed)

            challenge_channel = discord.utils.get(
                interaction.guild.text_channels, id=challenge["channel"]
            )

            try:
                await challenge_channel.edit(
                    name=interaction.channel.name.replace(
                        "❌", "🩸" if challenge["blooded"] else "✅"
                    )
                )
            except HTTPException:
                # We've exceeded the 2 channel edit per 10 min set by Discord.
                # This should only happen during testing, or when the users are trolling
                # by spamming solve and unsolve.
                pass

            challenge["solve_announcement"] = announcement.id

            MONGO[f"{DBNAME}"][CHALLENGE_COLLECTION].update_one(
                {"_id": challenge["_id"]},
                {
                    "$set": {
                        "solved": challenge["solved"],
                        "blooded": challenge["blooded"],
                        "solve_time": challenge["solve_time"],
                        "solve_announcement": challenge["solve_announcement"],
                        "players": challenge["players"],
                    }
                },
            )

            # Disable workon button for this challenge.
            announcements_channel = discord.utils.get(
                interaction.guild.text_channels,
                id=ctf["guild_channels"]["announcements"],
            )
            announcement = await announcements_channel.fetch_message(
                challenge["announcement"]
            )
            await announcement.edit(
                view=WorkonButton(name=challenge["name"], disabled=True)
            )

        elif status == "already_solved":
            await interaction.followup.send(
                "You already solved this challenge.", ephemeral=True
            )
        else:
            await interaction.followup.send("❌ Incorrect flag.", ephemeral=True)
