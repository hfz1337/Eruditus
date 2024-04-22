from typing import Generator, Optional

import aiohttp
from bs4 import BeautifulSoup

from config import CTFTIME_URL, USER_AGENT
from lib.util import truncate


async def scrape_event_info(event_id: int) -> Optional[dict]:
    """Scrape event information off the CTFtime website.

    Args:
        event_id: Unique ID of the event.

    Returns:
        A dictionary representing the event.
    """
    async with aiohttp.request(
        method="get",
        url=f"{CTFTIME_URL}/event/{event_id}",
        headers={"User-Agent": USER_AGENT()},
    ) as response:
        if response.status != 200:
            return None
        parser = BeautifulSoup(await response.text(), "html.parser")

    event_name = parser.find("h2").text.strip()
    event_location = parser.select_one("p b").text.strip()
    event_logo = parser.select_one(".span2 img")["src"].lstrip("/")
    event_format = parser.select_one("p:nth-child(5)").text.split(": ")[1].strip()
    event_weight = parser.select_one("p:nth-child(8)")
    if event_weight:
        event_website = parser.select_one("p:nth-child(6) a").text
    else:
        event_weight = parser.select_one("p:nth-child(7)")
        event_website = ""
    event_weight = (
        event_weight.text.split(": ")[1].strip()
        if ": " in event_weight.text
        else event_weight.text
    )
    event_organizers = [
        organizer.text.strip() for organizer in parser.select(".span10 li a")
    ]
    event_start, event_end = (
        parser.select_one(".span10 p:nth-child(1)").text.strip().split(" — ")
    )

    # Get rid of anchor elements to parse the description and prizes correctly.
    for anchor in parser.findAll("a"):
        anchor.replaceWithChildren()
    # Replace br tags with a linebreak.
    for br in parser.findAll("br"):
        br.replaceWith("\n")

    event_description = (
        "\n".join(p.getText() for p in parser.select("#id_description p"))
        or r"No description ¯\_(ツ)_/¯"
    )
    event_prizes = "\n".join(p.getText() for p in parser.select("h3+ .well p"))
    event_prizes = event_prizes or "No prizes."

    # Check if the logo actually exists and doesn't 404s.
    # In case it doesn't exist, we fall back to the event's logo.
    async with aiohttp.request(
        method="get",
        url=f"{CTFTIME_URL}/{event_logo}",
        headers={"User-Agent": USER_AGENT()},
    ) as response:
        if response.status == 404:
            async with aiohttp.request(
                method="get",
                url=f"{CTFTIME_URL}/api/v1/events/{event_id}/",
                headers={"User-Agent": USER_AGENT()},
            ) as event_resp:
                event_logo = (await event_resp.json())["logo"]
        else:
            event_logo = f"{CTFTIME_URL}/{event_logo}"

    return {
        "id": event_id,
        "name": event_name,
        "description": truncate(event_description),
        "prizes": truncate(event_prizes),
        "location": event_location,
        "format": event_format,
        "website": event_website,
        "logo": event_logo,
        "weight": event_weight,
        "organizers": event_organizers,
        "start": event_start,
        "end": event_end,
    }


async def scrape_current_events() -> Generator[dict, None, None]:
    """Scrape current events off the CTFtime home page.

    Yields:
        An integer representing the unique ID of the event.
    """
    async with aiohttp.request(
        method="get", url=CTFTIME_URL, headers={"User-Agent": USER_AGENT()}
    ) as response:
        if response.status != 200:
            return
        parser = BeautifulSoup(await response.text(), "html.parser")

    # Get ongoing events from the home page.
    event_ids = [
        int(event["href"].split("/")[-1]) for event in parser.select("td span+ a")
    ]

    for event_id in event_ids:
        yield await scrape_event_info(event_id)
