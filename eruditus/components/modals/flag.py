from datetime import datetime

import discord
from components.buttons.workon import WorkonButton
from constants import EmbedColours, Emojis, ThreadPrefixes
from db.challenge_repository import ChallengeRepository
from db.ctf_repository import CTFRepository
from platforms import PlatformCTX, match_platform
from platforms.base import SubmittedFlagState
from utils.discord import mark_if_maxed, parse_challenge_solvers
from utils.responses import send_response

_ctf_repo = CTFRepository()
_challenge_repo = ChallengeRepository()


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

        challenge = _challenge_repo.get_challenge_info(thread=interaction.channel_id)
        if challenge is None:
            await send_response(
                interaction,
                f"{Emojis.ERROR} Run this command from within a challenge thread.",
            )
            return

        ctf = _ctf_repo.get_ctf_info(guild_category=interaction.channel.category_id)

        ctx = PlatformCTX.from_credentials(ctf["credentials"])
        platform = await match_platform(ctx)
        if platform is None:
            await send_response(
                interaction,
                f"{Emojis.ERROR} Failed to submit the flag (unsupported platform).",
            )
            return

        result = await platform.impl.submit_flag(ctx, challenge["id"], self.flag.value)
        if result is None:
            await send_response(
                interaction, f"{Emojis.ERROR} Failed to submit the flag."
            )
            return

        error_messages: dict[SubmittedFlagState, str] = {
            SubmittedFlagState.ALREADY_SUBMITTED: "You already solved this challenge.",
            SubmittedFlagState.INCORRECT: f"{Emojis.ERROR} Incorrect flag.",
            SubmittedFlagState.CTF_NOT_STARTED: f"{Emojis.ERROR} CTF not started.",
            SubmittedFlagState.CTF_PAUSED: f"{Emojis.ERROR} CTF is paused.",
            SubmittedFlagState.CTF_ENDED: f"{Emojis.ERROR} CTF ended.",
            SubmittedFlagState.INVALID_CHALLENGE: f"{Emojis.ERROR} Invalid challenge.",
            SubmittedFlagState.INVALID_USER: f"{Emojis.ERROR} Invalid user.",
            SubmittedFlagState.RATE_LIMITED: f"{Emojis.ERROR} Rate limited.",
            SubmittedFlagState.UNKNOWN: f"{Emojis.ERROR} Unknown error.",
        }

        if result.state in error_messages:
            error_msg = error_messages.get(result.state)
            if result.retries is not None:
                error_msg += f" / {result.retries.left} retries left"
            await send_response(interaction, error_msg)
            return

        if result.state != SubmittedFlagState.CORRECT:
            await send_response(
                interaction, f"Unknown state: {result.state.name} {result.state.value}"
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
            await send_response(
                interaction, f"{Emojis.FIRST_BLOOD} Well done, you got first blood!"
            )
            embed = discord.Embed(
                title=f"{Emojis.FIRST_BLOOD} First blood!",
                description=(
                    f"**{', '.join(solvers)}** just blooded "
                    f"**{challenge['name']}** from the "
                    f"**{challenge['category']}** category!"
                ),
                colour=EmbedColours.FIRST_BLOOD,
                timestamp=datetime.now(),
            ).set_thumbnail(url=interaction.user.display_avatar.url)
        else:
            await send_response(
                interaction, f"{Emojis.SUCCESS} Well done, challenge solved!"
            )
            embed = discord.Embed(
                title=f"{Emojis.CELEBRATION} Challenge solved!",
                description=(
                    f"**{', '.join(solvers)}** just solved "
                    f"**{challenge['name']}** from the "
                    f"**{challenge['category']}** category!"
                ),
                colour=EmbedColours.SUCCESS,
                timestamp=datetime.now(),
            ).set_thumbnail(url=interaction.user.display_avatar.url)
        announcement = await solves_channel.send(embed=embed)

        challenge_thread = discord.utils.get(
            interaction.guild.threads, id=challenge["thread"]
        )

        challenge["solve_announcement"] = announcement.id

        _challenge_repo.update_solve_details(
            challenge_id=challenge["_id"],
            solved=challenge["solved"],
            blooded=challenge["blooded"],
            solve_time=challenge["solve_time"],
            solve_announcement=challenge["solve_announcement"],
            players=challenge["players"],
            flag=challenge["flag"],
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
        new_prefix = ThreadPrefixes.get_prefix(
            solved=True, blooded=challenge["blooded"]
        )
        await challenge_thread.edit(
            name=interaction.channel.name.replace(ThreadPrefixes.UNSOLVED, new_prefix)
        )

        # Mark the CTF category maxed if all its challenges were solved.
        await mark_if_maxed(interaction.channel.parent, challenge["category"])
