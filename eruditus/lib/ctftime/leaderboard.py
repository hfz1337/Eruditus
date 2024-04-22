import os
from typing import Optional

import aiohttp
from bs4 import BeautifulSoup

from config import CTFTIME_URL, USER_AGENT
from lib.ctftime.types import LeaderboardEntry


async def get_ctftime_leaderboard(
    year: Optional[int] = None, country_code: Optional[str] = None, n: int = 20
) -> Optional[dict[int, LeaderboardEntry]]:
    """Retrieve the CTFtime leaderboard.

    Args:
        year: The year for which to retrieve the leaderboard (default: current year).
        country_code: The country for which to retrieve the leaderboard (e.g., PS), if
            this parameter is not given, the global leaderboard is retrieved instead.
        n: Number of entries to retrieve (default: 20, max: 50).

    Returns:
        A dictionary of leaderboard entries (in descending order), mapping team IDs to
        a LeaderboardEntry item.
    """
    # Request the leaderboard from CTFtime.
    path = os.path.join("stats", str(year or ""), country_code or "")
    async with aiohttp.request(
        method="get",
        url=f"{CTFTIME_URL}/{path}",
        headers={"User-Agent": USER_AGENT()},
    ) as response:
        if response.status != 200:
            return None

        parser = BeautifulSoup(await response.text(), "html.parser")

    # Select the table rows.
    if not (rows := parser.select(".table-striped").pop(0).select("tr:has(td)")):
        return None

    return {
        (
            team_id := int(
                row.select_one("td:not(.country):has(a)")
                .find("a")["href"]
                .split("/")
                .pop()
            )
        ): LeaderboardEntry(
            position=int(row.select_one(".place").text.strip()),
            country_position=int(row.select(".place").pop().text.strip())
            if country_code
            else None,
            team_id=team_id,
            team_name=row.select_one("td:not(.country):has(a)").text.strip(),
            country_code=country_code
            or (row.find("img")["alt"] if row.find("img") else None),
            points=float(
                row.select("td:not(.place):not(.country):not(:has(a))")[-2].text
            ),
            events=int(
                row.select("td:not(.place):not(.country):not(:has(a))")[-1].text
            ),
        )
        for row in rows[:n]
    }
