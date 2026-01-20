"""Background task for tracking CTFtime team performance."""

from typing import TYPE_CHECKING

from config import CTFTIME_TEAM_ID, CTFTIME_TRACKING_CHANNEL, GUILD_ID
from constants import Emojis
from discord.ext import tasks
from integrations.ctftime import CTFTimeDiffType, get_ctftime_team_info

if TYPE_CHECKING:
    from eruditus import Eruditus


def create_ctftime_team_tracker(client: "Eruditus") -> tasks.Loop:
    """Create the CTFtime team tracking task.

    Args:
        client: The Discord bot client.

    Returns:
        The configured task loop.
    """

    @tasks.loop(minutes=15, reconnect=True)
    async def ctftime_team_tracking() -> None:
        """Track CTFtime team performance and post updates."""
        await client.wait_until_ready()

        if not CTFTIME_TRACKING_CHANNEL or not CTFTIME_TEAM_ID:
            ctftime_team_tracking.stop()
            return

        guild = client.get_guild(GUILD_ID)
        channel = guild.get_channel(CTFTIME_TRACKING_CHANNEL) if guild else None
        if not channel:
            return

        team_info = await get_ctftime_team_info(CTFTIME_TEAM_ID)
        if not team_info:
            return

        if not client.previous_team_info:
            client.previous_team_info = team_info
            return

        msg_fmt = "{} {} changed from {} to {}"
        diff = client.previous_team_info - team_info

        for update_type in diff:
            if update_type == CTFTimeDiffType.OVERALL_POINTS_UPDATE:
                if (
                    abs(
                        client.previous_team_info.overall_points
                        - team_info.overall_points
                    )
                    < 1
                ):
                    continue
                decreased = (
                    client.previous_team_info.overall_points > team_info.overall_points
                )
                msg = msg_fmt.format(
                    Emojis.CHART_DOWN if decreased else Emojis.CHART_UP,
                    "Overall points",
                    client.previous_team_info.overall_points,
                    team_info.overall_points,
                )
                await channel.send(msg)

            elif update_type == CTFTimeDiffType.OVERALL_PLACE_UPDATE:
                msg = msg_fmt.format(
                    Emojis.GLOBE_AMERICAS,
                    "Global position",
                    client.previous_team_info.overall_rating_place,
                    team_info.overall_rating_place,
                )
                await channel.send(msg)

            elif update_type == CTFTimeDiffType.COUNTRY_PLACE_UPDATE:
                msg = msg_fmt.format(
                    f":flag_{team_info.country_code.lower()}:",
                    "Country position",
                    client.previous_team_info.country_place,
                    team_info.country_place,
                )
                await channel.send(msg)

            elif update_type == CTFTimeDiffType.EVENT_UPDATE:
                event_msg = (
                    "There was an update to the `{}` event:\n"
                    "```diff\n"
                    f"  {'Place'} {'Event':<30} {'CTF points':<15} "
                    f"{'Rating points':<15}\n"
                    "- {} {} {} {}\n"
                    "+ {} {} {} {}\n"
                    "```"
                )
                for event_diff in diff[CTFTimeDiffType.EVENT_UPDATE]:
                    if (
                        abs(event_diff[0].rating_points - event_diff[1].rating_points)
                        < 1
                    ):
                        continue
                    await channel.send(
                        event_msg.format(
                            event_diff[0].event_name,
                            f"{event_diff[0].place:<5}",
                            f"{event_diff[0].event_name:<30}",
                            f"{event_diff[0].ctf_points:<15.4f}",
                            f"{event_diff[0].rating_points:<15.4f}",
                            f"{event_diff[1].place:<5}",
                            f"{event_diff[1].event_name:<30}",
                            f"{event_diff[1].ctf_points:<15.4f}",
                            f"{event_diff[1].rating_points:<15.4f}",
                        )
                    )

        client.previous_team_info = team_info

    return ctftime_team_tracking
