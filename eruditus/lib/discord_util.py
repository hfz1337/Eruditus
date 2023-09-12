import re
from datetime import datetime
from typing import Optional

import aiohttp
import discord

from config import (
    CHALLENGE_COLLECTION,
    CTF_COLLECTION,
    DBNAME,
    MAX_CONTENT_SIZE,
    MONGO,
    TEAM_NAME,
)
from lib.platforms import PlatformCTX, match_platform
from lib.util import plot_scoreboard


class Interaction(discord.Interaction):
    """Custom interaction class that would be used only within the typehints

    Notes:
        - This is needed because PyCharm can't resolve the response property
            as a property :shrug:
    """

    @property
    def response(self) -> discord.InteractionResponse:
        return None  # type: ignore


async def get_ctf_info(
    interaction: discord.Interaction, name: Optional[str] = None
) -> Optional[dict]:
    # Trying to find ctf by channel category
    if name is None:
        ctf = MONGO[DBNAME][CTF_COLLECTION].find_one(
            {"guild_category": interaction.channel.category_id}
        )

        if ctf is None:
            await interaction.followup.send(
                (
                    "Run this command from within a CTF channel, or provide the "
                    "name of the CTF you wish to delete."
                )
            )
            return None

        return ctf

    # Trying to find ctf by provided name
    ctf = MONGO[DBNAME][f"{CTF_COLLECTION}"].find_one(
        {"name": re.compile(f"^{re.escape(name.strip())}$", re.IGNORECASE)}
    )
    if ctf is None:
        await interaction.followup.send("No such CTF.")
        return None

    return ctf


async def get_challenge_solvers(
    interaction: discord.Interaction, challenge: dict, members: Optional[str] = None
) -> list[str]:
    if interaction.user.name not in challenge["players"]:
        challenge["players"].append(interaction.user.name)

    result: list[str] = [interaction.user.name]

    if members is None:
        return result

    for mention in re.split(r"<@!?([0-9]{15,20})>", members):
        if mention == "":
            continue

        # If id and we can fetch the user
        if re.match(r"^[0-9]{15,20}$", mention):
            member_info = await interaction.guild.fetch_member(int(mention))

            if member_info:
                result.append(member_info.name)
                continue

        # Otherwise, adding as a plain text
        result.extend(mention.split())

    return result


async def mark_if_maxed(interaction: discord.Interaction, challenge: dict) -> None:
    solved_states = MONGO[DBNAME][CHALLENGE_COLLECTION].aggregate(
        [
            {"$match": {"category": challenge["category"]}},
            {"$project": {"_id": 0, "solved": 1}},
        ]
    )
    if any(not state["solved"] for state in solved_states):
        return

    text_channel = interaction.channel.parent
    if text_channel.name.startswith("🔄"):
        await text_channel.edit(name=text_channel.name.replace("🔄", "🎯"))


async def add_challenge_solver(
    interaction: discord.Interaction, challenge: dict
) -> discord.Thread:
    challenge["players"].append(interaction.user.name)

    challenge_thread = discord.utils.get(
        interaction.guild.threads, id=challenge["thread"]
    )

    await challenge_thread.add_user(interaction.user)

    MONGO[DBNAME][CHALLENGE_COLLECTION].update_one(
        {"_id": challenge["_id"]},
        {"$set": {"players": challenge["players"]}},
    )

    return challenge_thread


async def remove_challenge_solver(
    interaction: discord.Interaction, challenge: dict, send_msg: bool = True
) -> discord.Thread:
    challenge["players"].remove(interaction.user.name)

    MONGO[DBNAME][CHALLENGE_COLLECTION].update_one(
        {"_id": challenge["_id"]},
        {"$set": {"players": challenge["players"]}},
    )

    challenge_thread = discord.utils.get(
        interaction.guild.threads, id=challenge["thread"]
    )

    if send_msg:
        await challenge_thread.send(
            f"{interaction.user.mention} left you alone, what a chicken! 🐥"
        )

    await challenge_thread.remove_user(interaction.user)
    return challenge_thread


async def send_scoreboard(
    ctf: dict,
    interaction: Optional[discord.Interaction] = None,
    guild: Optional[discord.Guild] = None,
) -> None:
    assert interaction or guild

    guild = guild if guild else interaction.guild

    async def followup(text: str, ephemeral: bool = False) -> None:
        if not interaction:
            return

        await interaction.followup.send(text, ephemeral=ephemeral)

    if ctf["credentials"]["url"] is None:
        await followup("No credentials set for this CTF.")
        return

    ctx: PlatformCTX = PlatformCTX.from_credentials(ctf["credentials"])
    platform = await match_platform(ctx)
    if not platform:
        await followup("Invalid URL set for this CTF, or platform isn't supported.")
        return

    try:
        teams = [x async for x in platform.pull_scoreboard(ctx)]
    except aiohttp.InvalidURL:
        await followup(
            "Invalid URL set for this CTF.",
            ephemeral=True,
        )
        return
    except aiohttp.ClientError:
        await followup(
            "Could not communicate with the CTF platform, please try again.",
            ephemeral=True,
        )
        return

    if not teams:
        await followup("Failed to fetch the scoreboard.", ephemeral=True)
        return

    me = await platform.get_me(ctx)
    our_team_name: str = me.name if me is not None else TEAM_NAME

    name_field_width = max(len(team.name) for team in teams) + 10
    message = (
        f"**Scoreboard as of "
        f"<t:{datetime.now().timestamp():.0f}>**"
        "```diff\n"
        f"  {'Rank':<10}{'Team':<{name_field_width}}{'Score'}\n"
        "{}"
        "```"
    )
    scoreboard = ""
    for rank, team in enumerate(teams, start=1):
        line = (
            f"{['-', '+'][team.name == our_team_name]} "
            f"{rank:<10}{team.name:<{name_field_width}}"
            f"{round(team.score or 0, 4)}\n"
        )
        if len(message) + len(scoreboard) + len(line) - 2 > MAX_CONTENT_SIZE:
            break
        scoreboard += line

    if scoreboard:
        message = message.format(scoreboard)
    else:
        message = "No solves yet, or platform isn't supported."

    graph_data = await platform.pull_scoreboard_datapoints(ctx)
    graph = (
        None
        if graph_data is None
        else discord.File(plot_scoreboard(graph_data), filename="scoreboard.png")
    )

    # Update scoreboard in the scoreboard channel.
    scoreboard_channel = discord.utils.get(
        guild.text_channels, id=ctf["guild_channels"]["scoreboard"]
    )
    async for last_message in scoreboard_channel.history(limit=1):
        await last_message.edit(content=message, attachments=[graph])
        break
    else:
        await scoreboard_channel.send(message, file=graph)

    if graph:
        graph.fp.seek(0)

    if interaction:
        await interaction.followup.send(message, file=graph)


async def save_credentials(interaction: discord.Interaction, credentials: dict) -> None:
    ctf = MONGO[DBNAME][CTF_COLLECTION].find_one(
        {"guild_category": interaction.channel.category_id}
    )
    MONGO[DBNAME][CTF_COLLECTION].update_one(
        {"_id": ctf["_id"]},
        {"$set": {"credentials": credentials}},
    )

    creds_channel = discord.utils.get(
        interaction.guild.text_channels, id=ctf["guild_channels"]["credentials"]
    )
    await creds_channel.purge()
    await creds_channel.send(credentials["_message"], suppress_embeds=True)
