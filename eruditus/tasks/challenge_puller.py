"""Background task for pulling challenges from CTF platforms."""

from datetime import datetime
from typing import TYPE_CHECKING

import aiohttp
import discord
from bson import ObjectId
from components.buttons.workon import WorkonButton
from config import GUILD_ID
from constants import EmbedColours, Emojis, ThreadPrefixes
from db.challenge_repository import ChallengeRepository
from db.ctf_repository import CTFRepository
from discord.ext import tasks
from platforms import PlatformCTX, match_platform
from utils.discord import get_challenge_category_channel
from utils.formatting import sanitize_channel_name, truncate

_ctf_repo = CTFRepository()
_challenge_repo = ChallengeRepository()

if TYPE_CHECKING:
    from eruditus import Eruditus


def create_challenge_puller_task(client: "Eruditus") -> tasks.Loop:
    """Create the challenge puller task.

    Args:
        client: The Discord bot client.

    Returns:
        The configured task loop.
    """

    @tasks.loop(minutes=2, reconnect=True)
    async def challenge_puller() -> None:
        """Periodically pull challenges for all running CTFs."""
        client.challenge_puller_is_running = True

        await client.wait_until_ready()

        guild = client.get_guild(GUILD_ID)
        if not guild:
            client.challenge_puller_is_running = False
            return

        for ctf in _ctf_repo.find_not_ended():
            url = ctf["credentials"]["url"]

            if url is None:
                continue

            category_channel = discord.utils.get(
                guild.categories, id=ctf["guild_category"]
            )

            ctx = PlatformCTX.from_credentials(ctf["credentials"])
            try:
                platform = await match_platform(ctx)
            except aiohttp.ClientError:
                continue

            if platform is None:
                continue

            async for challenge in platform.impl.pull_challenges(ctx):
                if challenge.solved_by_me:
                    continue

                challenge.category = challenge.category.title().strip()

                if _challenge_repo.get_challenge_info(
                    id=challenge.id, name=challenge.name, category=challenge.category
                ):
                    continue

                description = (
                    "\n".join(
                        (
                            challenge.description,
                            (
                                f"`{challenge.connection_info}`"
                                if challenge.connection_info is not None
                                else ""
                            ),
                        )
                    )
                    or "No description."
                )
                tags = ", ".join(challenge.tags or []) or "No tags."

                files = []
                for file in challenge.files:
                    if file.name is not None:
                        hyperlink = f"[{file.name}]({file.url})"
                    else:
                        hyperlink = file.url
                    files.append(hyperlink)

                files_str = "No files."
                if len(files) > 0:
                    files_str = "\n- ".join(files)
                files_str = "\n- " + files_str

                img_attachments = []
                img_urls = []
                for image in challenge.images or []:
                    if image.url.startswith(ctx.base_url):
                        raw_image = await platform.impl.fetch(ctx, image.url)
                        if raw_image is None:
                            continue
                        attachment = discord.File(raw_image, filename=image.name)
                        img_attachments.append(attachment)
                    else:
                        img_urls.append(image.url)

                embed = discord.Embed(
                    title=f"{challenge.name} - {challenge.value} points",
                    description=truncate(
                        f"**Category:** {challenge.category}\n"
                        f"**Description:** {description}\n"
                        f"**Files:** {files_str}\n"
                        f"**Tags:** {tags}",
                        max_len=4096,
                    ),
                    colour=EmbedColours.INFO,
                    timestamp=datetime.now(),
                )

                if img_urls:
                    embed.set_image(url=img_urls.pop(0))

                text_channel = await get_challenge_category_channel(
                    guild, category_channel, challenge.category
                )

                thread_name = sanitize_channel_name(challenge.name)
                challenge_thread = await text_channel.create_thread(
                    name=f"{ThreadPrefixes.UNSOLVED}{thread_name}", invitable=False
                )

                message = await challenge_thread.send(embed=embed)

                for img_url in img_urls:
                    await challenge_thread.send(content=img_url)
                if img_attachments:
                    await challenge_thread.send(files=img_attachments)

                await message.pin()

                challenge_oid = ObjectId()

                announcements_channel = discord.utils.get(
                    guild.text_channels,
                    id=ctf["guild_channels"]["announcements"],
                )
                role = discord.utils.get(guild.roles, id=ctf["guild_role"])

                embed = discord.Embed(
                    title=f"{Emojis.BELL} New challenge created!",
                    description=(
                        f"**Challenge name:** {challenge.name}\n"
                        f"**Category:** {challenge.category}\n\n"
                        f"Use `/ctf workon {challenge.name}` or the button to join."
                        f"\n{role.mention}"
                    ),
                    colour=EmbedColours.SUCCESS,
                    timestamp=datetime.now(),
                )
                announcement = await announcements_channel.send(
                    embed=embed, view=WorkonButton(oid=challenge_oid)
                )

                _challenge_repo.create(
                    {
                        "_id": challenge_oid,
                        "id": challenge.id,
                        "name": challenge.name,
                        "category": challenge.category,
                        "thread": challenge_thread.id,
                        "solved": False,
                        "blooded": False,
                        "players": [],
                        "announcement": announcement.id,
                        "solve_time": None,
                        "solve_announcement": None,
                    }
                )

                _ctf_repo.add_challenge(ctf["_id"], challenge_oid)
                ctf["challenges"].append(challenge_oid)

                await text_channel.edit(
                    name=text_channel.name.replace(
                        Emojis.SLEEPING, Emojis.ACTIVE
                    ).replace(Emojis.MAXED, Emojis.ACTIVE)
                )

        client.challenge_puller_is_running = False

    return challenge_puller
