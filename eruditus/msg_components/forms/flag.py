from datetime import datetime

import discord

from config import CHALLENGE_COLLECTION, DBNAME, MONGO
from lib.discord_util import mark_if_maxed, parse_challenge_solvers
from lib.platforms import PlatformCTX, match_platform
from lib.platforms.abc import SubmittedFlagState
from lib.util import get_challenge_info, get_ctf_info
from msg_components.buttons.workon import WorkonButton


class FlagSubmissionForm(discord.ui.Modal, title="Flag submission form"):
    flag = discord.ui.TextInput(
        label="Flag",
        placeholder=r"ctf{s0m3th1ng_l33t}",
    )

    def __init__(self, members: str) -> None:
        super().__init__()
        self.members = members

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        members = self.members

        challenge = get_challenge_info(thread=interaction.channel_id)
        if challenge is None:
            await interaction.followup.send(
                "❌ This command may only be used from within a challenge thread.",
                ephemeral=True,
            )
            return

        ctf = get_ctf_info(guild_category=interaction.channel.category_id)

        ctx = PlatformCTX.from_credentials(ctf["credentials"])
        platform = await match_platform(ctx)
        if platform is None:
            await interaction.followup.send(
                "❌ Failed to submit the flag (unsupported platform).",
                ephemeral=True,
            )
            return

        result = await platform.submit_flag(ctx, challenge["id"], self.flag.value)
        if result is None:
            await interaction.followup.send("❌ Failed to submit the flag.")
            return

        error_messages: dict[SubmittedFlagState, str] = {
            SubmittedFlagState.ALREADY_SUBMITTED: "You already solved this challenge.",
            SubmittedFlagState.INCORRECT: "❌ Incorrect flag.",
            SubmittedFlagState.CTF_NOT_STARTED: "❌ CTF not started.",
            SubmittedFlagState.CTF_PAUSED: "❌ CTF is paused.",
            SubmittedFlagState.CTF_ENDED: "❌ CTF ended.",
            SubmittedFlagState.INVALID_CHALLENGE: "❌ Invalid challenge.",
            SubmittedFlagState.INVALID_USER: "❌ Invalid user.",
            SubmittedFlagState.RATE_LIMITED: "❌ Rate limited.",
            SubmittedFlagState.UNKNOWN: "❌ Unknown error.",
        }

        if result.state in error_messages:
            error_msg = error_messages.get(result.state)
            if result.retries is not None:
                error_msg += f" / {result.retries.left} retries left"
            await interaction.followup.send(error_msg)
            return

        if result.state != SubmittedFlagState.CORRECT:
            await interaction.followup.send(
                f"Unknown state: {result.state.name} {result.state.value}"
            )
            return

        # Announce that the challenge was solved.
        challenge["solved"] = True
        challenge["solve_time"] = int(datetime.now().timestamp())
        challenge["flag"] = self.flag.value

        solves_channel = interaction.client.get_channel(ctf["guild_channels"]["solves"])
        solvers = await parse_challenge_solvers(interaction, challenge, members)

        if result.is_first_blood:
            challenge["blooded"] = True
            await interaction.followup.send("🩸 Well done, you got first blood!")
            embed = discord.Embed(
                title="🩸 First blood!",
                description=(
                    f"**{', '.join(solvers)}** just blooded "
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
                    f"**{', '.join(solvers)}** just solved "
                    f"**{challenge['name']}** from the "
                    f"**{challenge['category']}** category!"
                ),
                colour=discord.Colour.dark_gold(),
                timestamp=datetime.now(),
            ).set_thumbnail(url=interaction.user.display_avatar.url)
        announcement = await solves_channel.send(embed=embed)

        challenge_thread = discord.utils.get(
            interaction.guild.threads, id=challenge["thread"]
        )

        challenge["solve_announcement"] = announcement.id

        MONGO[DBNAME][CHALLENGE_COLLECTION].update_one(
            {"_id": challenge["_id"]},
            {
                "$set": {
                    "solved": challenge["solved"],
                    "blooded": challenge["blooded"],
                    "solve_time": challenge["solve_time"],
                    "solve_announcement": challenge["solve_announcement"],
                    "players": challenge["players"],
                    "flag": challenge["flag"],
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
        await announcement.edit(view=WorkonButton(oid=challenge["_id"], disabled=True))

        # We leave editing the channel name till the end since we might get rate
        # limited, causing a sleep that will block this function call.
        await challenge_thread.edit(
            name=interaction.channel.name.replace(
                "❌", "🩸" if challenge["blooded"] else "✅"
            )
        )

        # Mark the CTF category maxed if all its challenges were solved.
        await mark_if_maxed(interaction.channel.parent, challenge["category"])
