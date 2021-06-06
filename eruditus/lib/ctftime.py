from typing import Generator
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from config import CTFTIME_URL, USER_AGENT
from lib.util import truncate


def scrape_event_info(event_id: int) -> dict:
    """Scrapes event information off the CTFtime website.

    Args:
        event_id: Unique ID of the event.

    Returns:
        A dictionary representing the event.

    """
    # The date format used by CTFtime
    ctftime_date_format = "%a, %d %B %Y, %H:%M"

    response = requests.get(
        url=f"{CTFTIME_URL}/event/{event_id}", headers={"User-Agent": USER_AGENT}
    )
    if response.status_code != 200:
        return None

    parser = BeautifulSoup(response.content, "html.parser")

    event_name = parser.find("h2").text.strip()
    event_location = parser.select_one("p b").text.strip()
    event_format = parser.select_one("p:nth-child(5)").text.split(": ")[1].strip()
    event_website = parser.select_one("p:nth-child(6) a").text
    event_logo = parser.select_one(".span2 img")["src"]
    event_weight = parser.select_one("p:nth-child(8)").text.split(": ")[1].strip()
    event_organizers = [
        organizer.text.strip() for organizer in parser.select(".span10 li a")
    ]
    event_start, event_end = (
        parser.select_one(".span10 p:nth-child(1)")
        .text.replace(" UTC", "")
        .strip()
        .split(" — ")
    )
    # Convert dates to timestamps
    event_start = datetime.strptime(event_start, ctftime_date_format).timestamp()
    event_end = datetime.strptime(event_end, ctftime_date_format).timestamp()

    # Get rid of anchor elements to parse the description and prizes correctly
    for anchor in parser.findAll("a"):
        anchor.replaceWithChildren()
    # Replace br tags with a linebreak
    for br in parser.findAll("br"):
        br.replaceWith("\n")

    event_description = "\n".join(
        p.getText() for p in parser.select("#id_description p")
    )
    event_prizes = "\n".join(p.getText() for p in parser.select("h3+ .well p"))
    event_prizes = event_prizes or "No prizes."

    return {
        "id": event_id,
        "name": event_name,
        "description": truncate(event_description),
        "prizes": truncate(event_prizes),
        "location": event_location,
        "format": event_format,
        "website": event_website,
        "logo": f"{CTFTIME_URL}{event_logo}",
        "weight": event_weight,
        "organizers": event_organizers,
        "start": event_start,
        "end": event_end,
    }


def scrape_current_events() -> Generator[int, None, None]:
    """Scrapes current events off the CTFtime home page.

    Yields:
        int: Unique ID of the event.
    """
    response = requests.get(url=CTFTIME_URL, headers={"User-Agent": USER_AGENT})
    parser = BeautifulSoup(response.content, "html.parser")

    # Get ongoing events from the home page
    event_ids = [
        int(event["href"].split("/")[-1]) for event in parser.select("td span+ a")
    ]

    for event_id in event_ids:
        yield scrape_event_info(event_id)
