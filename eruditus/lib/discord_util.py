import re
from datetime import datetime
from typing import Optional

import aiohttp
import discord
from discord import InteractionResponseType

from config import (
    CHALLENGE_COLLECTION,
    CTF_COLLECTION,
    DBNAME,
    MAX_CONTENT_SIZE,
    MONGO,
    TEAM_NAME,
)
from lib.platforms import PlatformCTX, match_platform
from lib.util import get_ctf_info, plot_scoreboard, sanitize_channel_name


def is_deferred(interaction: discord.Interaction) -> bool:
    """Check whether an interaction was deferred previously.

    Args:
        interaction: The Discord interaction.

    Returns:
        True if the interaction was deferred.
    """
    return interaction.response.type in {
        InteractionResponseType.deferred_channel_message,
        InteractionResponseType.deferred_message_update,
    }


async def parse_challenge_solvers(
    interaction: discord.Interaction, challenge: dict, members: Optional[str] = None
) -> list[str]:
    """Return a list of users who contributed in solving a challenge.

    Args:
        interaction: The Discord interaction.
        challenge: The challenge document.
        members: A string containing member mentions of those who contributed in solving
            the challenge (in addition to the member who triggered this interaction).

    Returns:
        A list of user names.
    """
    if interaction.user.name not in challenge["players"]:
        challenge["players"].append(interaction.user.name)

    return list(
        {interaction.user.name}
        | (
            set()
            if members is None
            else {
                member.name
                for member in await parse_member_mentions(interaction, members)
            }
        )
    )


async def parse_member_mentions(
    interaction: discord.Interaction, members: str
) -> list[discord.Member]:
    """Extract Discord members mentioned in a string.

    Args:
        interaction: The Discord interaction.
        members: A string containing member mentions.

    Returns:
        A list of Discord member objects.
    """
    return [
        member
        for member_id in re.findall(r"<@!?([0-9]{15,20})>", members)
        if (member := await interaction.guild.fetch_member(int(member_id)))
    ]


async def get_challenge_category_channel(
    guild: discord.Guild, ctf_category_channel: discord.CategoryChannel, category: str
) -> discord.TextChannel:
    """Retrieve the text channel associated to a challenge category or create it if it
    didn't exist.

    Args:
        guild: The Discord guild object.
        ctf_category_channel: The CTF category channel.
        category: The challenge category.

    Returns:
        The text channel associated to the CTF category.
    """
    channel_name = sanitize_channel_name(category)

    for prefix in ("💤", "🔄", "🎯"):
        if text_channel := discord.utils.get(
            guild.text_channels,
            category=ctf_category_channel,
            name=f"{prefix}-{channel_name}",
        ):
            return text_channel

    return await guild.create_text_channel(
        name=f"🔄-{channel_name}",
        category=ctf_category_channel,
        default_auto_archive_duration=10080,
    )


async def mark_if_maxed(text_channel: discord.TextChannel, category: str) -> None:
    """Indicate that a CTF category is maxed in case all its challenges are solved.

    Args:
        text_channel: The text channel associated to the CTF category.
        category: The CTF category.
    """
    solved_states = MONGO[DBNAME][CHALLENGE_COLLECTION].aggregate(
        [
            {"$match": {"category": category}},
            {"$project": {"_id": 0, "solved": 1}},
        ]
    )
    if any(not state["solved"] for state in solved_states):
        return

    if text_channel.name.startswith("🔄"):
        await text_channel.edit(name=text_channel.name.replace("🔄", "🎯"))


async def add_challenge_worker(
    challenge_thread: discord.Thread, challenge: dict, member: discord.member
) -> None:
    """Add a member to the list of people currently working on a challenge.

    Args:
        challenge_thread: The thread associated to the CTF challenge.
        challenge: The challenge document.
        member: The member to be added.
    """
    challenge["players"].append(member.name)
    MONGO[DBNAME][CHALLENGE_COLLECTION].update_one(
        {"_id": challenge["_id"]},
        {"$set": {"players": challenge["players"]}},
    )
    await challenge_thread.add_user(member)


async def remove_challenge_worker(
    challenge_thread: discord.Thread,
    challenge: dict,
    member: discord.Member,
) -> None:
    """Remove a member from the list of people currently working on a challenge.

    Args:
        challenge_thread: The thread associated to the CTF challenge.
        challenge: The challenge document.
        member: The member to be removed.
    """
    challenge["players"].remove(member.name)
    MONGO[DBNAME][CHALLENGE_COLLECTION].update_one(
        {"_id": challenge["_id"]},
        {"$set": {"players": challenge["players"]}},
    )
    await challenge_thread.remove_user(member)


async def send_scoreboard(
    ctf: dict,
    interaction: Optional[discord.Interaction] = None,
    guild: Optional[discord.Guild] = None,
) -> None:
    """Send or update the scoreboard in the scoreboard channel and eventually send it
    as a reply for the interaction if present.

    Args:
        ctf: The CTF document.
        interaction: The Discord interaction.
        guild: The Discord guild object.

    Raises:
        AssertionError: if both `guild` and `interaction` are not provided.
    """
    assert interaction or guild
    guild = guild or interaction.guild

    async def followup(content: str, ephemeral=True, **kwargs) -> None:
        if not interaction:
            return
        await interaction.followup.send(content, ephemeral=ephemeral, **kwargs)

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
        await followup("Invalid URL set for this CTF.")
        return
    except aiohttp.ClientError:
        await followup("Could not communicate with the CTF platform, please try again.")
        return

    if not teams:
        await followup("Failed to fetch the scoreboard.")
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

    scoreboard_channel = discord.utils.get(
        guild.text_channels, id=ctf["guild_channels"]["scoreboard"]
    )
    await update_scoreboard(scoreboard_channel, message, graph)
    await followup(message, ephemeral=False, file=graph)


async def update_scoreboard(
    scoreboard_channel: discord.TextChannel,
    message: str,
    graph: Optional[discord.File] = None,
) -> None:
    """Update scoreboard in the scoreboard channel.

    Args:
        scoreboard_channel: The Discord scoreboard channel.
        message: The scoreboard message.
        graph: The score graph to send along the message as a file attachment.

    Notes:
        This function resets the stream position after consuming the graph buffer.
    """
    async for last_message in scoreboard_channel.history(limit=1):
        kw = {"attachments": [graph]} if graph is not None else None
        await last_message.edit(content=message, **kw)
        break
    else:
        kw = {"file": graph} if graph is not None else None
        await scoreboard_channel.send(message, **kw)

    if graph:
        graph.fp.seek(0)


async def update_credentials(
    interaction: discord.Interaction, credentials: dict
) -> None:
    """Save CTF credentials in the database and update the message in the credentials
    channel.

    Args:
        interaction: The Discord interaction.
        credentials: The credentials dictionary.
    """
    ctf = get_ctf_info(guild_category=interaction.channel.category_id)
    MONGO[DBNAME][CTF_COLLECTION].update_one(
        {"_id": ctf["_id"]},
        {"$set": {"credentials": credentials}},
    )

    creds_channel = discord.utils.get(
        interaction.guild.text_channels, id=ctf["guild_channels"]["credentials"]
    )
    await creds_channel.purge()
    await creds_channel.send(credentials["_message"], suppress_embeds=True)
