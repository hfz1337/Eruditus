from typing import Optional

import aiohttp
from bs4 import BeautifulSoup, Tag

from config import CTFTIME_URL, USER_AGENT
from lib.ctftime.types import CTFTimeParticipatedEvent, CTFTimeTeam


async def get_ctftime_team_info(team_id: int) -> Optional[CTFTimeTeam]:
    # Request the team data from ctftime
    async with aiohttp.request(
        method="get",
        url=f"{CTFTIME_URL}/team/{team_id}",
        headers={"User-Agent": USER_AGENT},
    ) as response:
        # If CTFTime is doing CTFTime things
        if response.status != 200:
            return None

        parser = BeautifulSoup(await response.text(), "html.parser")

    # Select the panes with content
    panes = parser.select(".tab-pane")
    if len(panes) == 0:
        return None

    # Find rating pane
    rating_pane: Tag = panes[0]
    if "rating" not in rating_pane.get("id", ""):
        return None

    # Look up for the ranking info
    ranking_places: list[Tag] = rating_pane.select("p")
    if len(ranking_places) == 0:
        return None

    # At this time, we're 100% sure that we're at the right pane,
    # so we can finally init the result struct
    result = CTFTimeTeam(
        overall_points=0.0,
        overall_rating_place=0,
        country_place=None,
        participated_in=list(),
    )

    # Select the global ranking info
    overall_values = ranking_places[0].select("b")
    result.overall_rating_place = int(overall_values[0].text)
    result.overall_points = float(overall_values[1].text)

    # If there's a country place, we should store it
    if len(ranking_places) >= 2:
        result.country_place = int(ranking_places[1].find("b").text)

    # Look for the table with events
    events_table = rating_pane.find("table")
    events_entries = events_table.select("tr")

    # Start iteration at 1 because the first entry is always a table header
    for i in range(1, len(events_entries)):
        # Select the table cells
        tds = [x for x in events_entries[i].select("td")]

        # Assemble the scoreboard entry
        result.participated_in.append(
            CTFTimeParticipatedEvent(
                place=int(tds[1].text),
                event_name=tds[2].text,
                event_id=int(tds[2].contents[0].attrs.get("href", "0").split("/")[-1]),
                ctf_points=float(tds[3].text),
                rating_points=float(tds[4].text) if "*" not in tds[4].text else None,
            )
        )

    return result
