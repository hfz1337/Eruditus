import io
from datetime import datetime, timedelta
from typing import AsyncGenerator, Optional

import aiohttp
import discord
from bs4 import BeautifulSoup

from config import CTFTIME_URL, USER_AGENT
from lib.ctftime.misc import ctftime_date_to_datetime
from lib.platforms import PlatformCTX, match_platform
from lib.util import get_local_time, truncate


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


async def scrape_current_events() -> AsyncGenerator[dict, None]:
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


async def create_discord_events(guild: discord.Guild, current_loop: int = None) -> None:
    # Timezone aware local time.
    local_time = get_local_time()

    scheduled_events = {
        scheduled_event.name: scheduled_event.id
        for scheduled_event in guild.scheduled_events
    }
    async with aiohttp.request(
        method="get",
        url=f"{CTFTIME_URL}/api/v1/events/",
        params={"limit": "20"},
        headers={"User-Agent": USER_AGENT()},
    ) as response:
        if response.status == 200:
            for event in await response.json():
                event_start = None
                event_end = None

                event_info = await scrape_event_info(event["id"])
                if event_info is None:
                    # Cloudflare protection, unable to scrape the event page.
                    event_info = event
                    event_info["name"] = event_info["title"]
                    event_info["website"] = event_info["url"]
                    event_info["prizes"] = "Visit the event page for more information."
                    event_info["organizers"] = [
                        organizer["name"] for organizer in event_info["organizers"]
                    ]
                    event_start = datetime.fromisoformat(event_info["start"])
                    event_end = datetime.fromisoformat(event_info["finish"])

                if event_start is None or event_end is None:
                    event_start = ctftime_date_to_datetime(event_info["start"])
                    event_end = ctftime_date_to_datetime(event_info["end"])

                # Ignore event if start/end times are incorrect.
                if event_end <= event_start:
                    continue

                if event_start > local_time + timedelta(weeks=1):
                    continue

                # If the event starts in more than a week, then it's too soon to
                # schedule it, we ignore it for now.
                # But if it's not our first run, we make sure to not recreate
                # events that were already created, in order to avoid adding back
                # manually cancelled events.
                # Note: this only works for events added at least 7 days prior to
                # their start date in CTFtime, the other case should be rare.
                #
                #                            .-> E.g., events happening in this
                #                            |   window won't be recreated in the
                #                            |   second iteration.
                #              ,-------------`---------,
                #              v                       v
                #  |-----------|-----------------------|-----------|-------------->
                # t0        t0 + 3h                 7 days   (7 days + 3h)
                # `...,
                #     |
                # initial run
                if (
                    isinstance(current_loop, int)
                    and current_loop != 0
                    and event_start
                    <= local_time + timedelta(weeks=1) - timedelta(hours=3)
                ):
                    continue

                if event_info["logo"]:
                    async with aiohttp.request(
                        method="get",
                        url=event_info["logo"],
                        headers={"User-Agent": USER_AGENT()},
                    ) as image:
                        if image.status == 200:
                            raw_image = io.BytesIO(await image.read()).read()
                        else:
                            raw_image = None

                # Check if the platform is supported.
                ctx = PlatformCTX.from_credentials({"url": event_info["website"]})
                try:
                    platform = await match_platform(ctx)
                except aiohttp.ClientError:
                    platform = None

                event_description = (
                    f"{event_info['description']}\n\n"
                    f"👥 **Organizers**\n{', '.join(event_info['organizers'])}\n\n"
                    f"💰 **Prizes**\n{event_info['prizes']}\n\n"
                    f"⚙️ **Format**\n {event_info['location']} "
                    f"{event_info['format']}\n\n"
                    f"🎯 **Weight**\n{event_info['weight']}"
                )
                parameters = {
                    "name": event_info["name"],
                    "description": truncate(
                        text=(
                            f"**☑️ Supported platform ({platform.name})**\n\n"
                            if platform
                            else ""
                        )
                        + event_description,
                        max_len=1000,
                    ),
                    "start_time": event_start,
                    "end_time": event_end,
                    "entity_type": discord.EntityType.external,
                    "image": raw_image,
                    "location": truncate(
                        f"{CTFTIME_URL}/event/{event_info['id']}"
                        " — "
                        f"{event_info['website']}",
                        max_len=100,
                    ),
                    "privacy_level": discord.PrivacyLevel.guild_only,
                }

                # Remove image parameter if we couldn't fetch the logo.
                if raw_image is None:
                    parameters.pop("image")

                # In case the event was already scheduled, we update it, otherwise
                # we create a new event.
                if event_info["name"] in scheduled_events:
                    scheduled_event = guild.get_scheduled_event(
                        scheduled_events[event_info["name"]]
                    )
                    # We only update an event's date if it's more than 2 days away.
                    if local_time + timedelta(days=2) >= event_start:
                        parameters["start_time"] = scheduled_event.start_time
                        parameters["end_time"] = scheduled_event.end_time
                    await scheduled_event.edit(**parameters)

                else:
                    await guild.create_scheduled_event(**parameters)
