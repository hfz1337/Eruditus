import re
from typing import Dict

import discord
from discord import HTTPException

from datetime import datetime

from lib.platforms import match_platform
from lib.platforms import PlatformCTX
from lib.platforms.abc import SubmittedFlagState
from msg_components.buttons.workon import WorkonButton
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

    def __init__(self, members: str) -> None:
        super().__init__()
        self.members = members

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        members = self.members

        challenge = MONGO[f"{DBNAME}"][CHALLENGE_COLLECTION].find_one(
            {"channel": interaction.channel_id}
        )
        if challenge is None:
            await interaction.followup.send(
                "❌ This command may only be used from within a challenge channel."
            )
            return

        ctf = MONGO[f"{DBNAME}"][CTF_COLLECTION].find_one(
            {"guild_category": interaction.channel.category_id}
        )

        ctx = PlatformCTX.from_credentials(ctf['credentials'])
        platform = await match_platform(ctx)
        if platform is None:
            await interaction.followup.send("❌ Failed to submit the flag. / Unsupported platform")
            return

        result = await platform.submit_flag(
            ctx, challenge['id'], self.flag.value
        )
        if result is None:
            await interaction.followup.send("❌ Failed to submit the flag.")
            return

        error_messages: Dict[SubmittedFlagState, str] = {
            SubmittedFlagState.ALREADY_SUBMITTED: 'You already solved this challenge.',
            SubmittedFlagState.INCORRECT: '❌ Incorrect flag.',
            SubmittedFlagState.CTF_PAUSED: '❌ CTF is paused.',
            SubmittedFlagState.RATE_LIMITED: '❌ Rate limited.',
            SubmittedFlagState.UNKNOWN: '❌ Unknown error.',
        }

        if result.state in error_messages:
            error_msg = error_messages.get(result.state)
            if result.retries is not None:
                error_msg += f' / {result.retries.left} retries left'
            await interaction.followup.send(error_msg)
            return

        # @note: @es3n1n: Ignore other states, they should be handled within the `error_messages` dict
        if result.state != SubmittedFlagState.CORRECT:
            return

        # Announce that the challenge was solved.
        challenge["solved"] = True
        challenge["solve_time"] = int(datetime.now().timestamp())
        challenge["flag"] = self.flag.value

        solves_channel = interaction.client.get_channel(
            ctf["guild_channels"]["solves"]
        )

        # Add the user who triggered this interaction to the list of players, useful
        # in case the one who triggered the interaction is an admin.
        if interaction.user.name not in challenge["players"]:
            challenge["players"].append(interaction.user.name)

        solvers = [interaction.user.name] + (
            []
            if members is None
            else [
                member.name
                for member_id in re.findall(r"<@!?([0-9]{15,20})>", members)
                if (member := await interaction.guild.fetch_member(int(member_id)))
            ]
        )

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
        await announcement.edit(
            view=WorkonButton(name=challenge["name"], disabled=True)
        )
