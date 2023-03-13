from typing import Tuple, Generator
import re
import aiohttp
from bs4 import BeautifulSoup


async def is_ctfd_platform(ctfd_base_url: str) -> bool:
    """Check whether a website is using the CTFd framework.

    Args:
        ctfd_base_url: URL of the CTF platform to check for.

    Returns:
        True if the platform is using CTFd, else False.
    """
    async with aiohttp.request(
        method="get", url=f"{ctfd_base_url.strip()}/plugins/challenges/assets/view.js"
    ) as response:
        return "CTFd" in await response.text()


async def login(ctfd_base_url: str, username: str, password: str) -> dict:
    """Login to the CTFd platform.

    Args:
        ctfd_base_url: The CTFd platform to login into.
        username: The username to login with.
        password: The password to login with.

    Returns:
        A dictionary containing session cookies.
    """
    ctfd_base_url = ctfd_base_url.strip("/")

    # Confirm that we're dealing with a CTFd platform.
    if not await is_ctfd_platform(ctfd_base_url):
        return None

    # Get the nonce.
    async with aiohttp.request(method="get", url=f"{ctfd_base_url}/login") as response:
        cookies = {cookie.key: cookie.value for cookie in response.cookies.values()}
        nonce = BeautifulSoup(await response.text(), "html.parser").find(
            "input", {"id": "nonce"}
        )
        if nonce is None:
            return None
        nonce = nonce["value"]

    # Login to CTFd.
    data = {
        "name": username,
        "password": password,
        "_submit": "Submit",
        "nonce": nonce,
    }
    async with aiohttp.request(
        method="post",
        url=f"{ctfd_base_url}/login",
        data=data,
        cookies=cookies,
        allow_redirects=False,
    ) as response:
        return {cookie.key: cookie.value for cookie in response.cookies.values()}


async def submit_flag(
    ctfd_base_url: str, username: str, password: str, challenge_id: int, flag: str
) -> Tuple[str, bool]:
    """Attempt to submit the flag into the CTFd platform and check if we got first
    blood in case it succeeds.

    Args:
        ctfd_base_url: The CTFd platform to login into.
        username: The username to login with.
        password: The password to login with.
        challenge_id: ID of the challenge to the submit the flag for.
        flag: Flag of the challenge.

    Returns:
        A tuple containing the status message and a boolean indicating if we got
        first blood.
    """
    ctfd_base_url = ctfd_base_url.strip("/")

    cookies = await login(ctfd_base_url, username, password)
    if cookies is None:
        return (None, None)

    # Get CSRF token.
    async with aiohttp.request(
        method="get", url=f"{ctfd_base_url}/challenges", cookies=cookies
    ) as response:
        csrf_nonce = re.search(
            '(?<=csrfNonce\': ")[A-Fa-f0-9]+(?=")', await response.text()
        )
    if csrf_nonce is None:
        return (None, None)

    csrf_nonce = csrf_nonce.group(0)
    json = {"challenge_id": challenge_id, "submission": flag}
    async with aiohttp.request(
        method="post",
        url=f"{ctfd_base_url}/api/v1/challenges/attempt",
        json=json,
        cookies=cookies,
        headers={"CSRF-Token": csrf_nonce},
    ) as response:
        # Check if we got a response.
        if response.status == 200 and (json := await response.json())["success"]:
            # The flag was correct.
            if json["data"]["status"] == "correct":
                # Check if we got first blood.
                async with aiohttp.request(
                    method="get",
                    url=f"{ctfd_base_url}/api/v1/challenges/{challenge_id}",
                    cookies=cookies,
                    allow_redirects=False,
                ) as response:
                    if (
                        response.status == 200
                        and (json := await response.json())["success"]
                    ):
                        return ("correct", json["data"]["solves"] == 1)

                return ("correct", None)
            # We already solved this challenge, or the flag was incorrect.
            return (json["data"]["status"], None)

    return (None, None)


async def pull_challenges(
    ctfd_base_url: str, username: str, password: str
) -> Generator[dict, None, None]:
    """Pull new challenges from the CTFd platform.

    Args:
        ctfd_base_url: The CTFd platform to login into.
        username: The username to login with.
        password: The password to login with.

    Yields:
        A dictionary representing information about the challenge.
    """
    ctfd_base_url = ctfd_base_url.strip("/")

    # Confirm that we're dealing with a CTFd platform.
    if not await is_ctfd_platform(ctfd_base_url):
        return

    cookies = await login(ctfd_base_url, username, password)

    # Get challenges.
    async with aiohttp.request(
        method="get",
        url=f"{ctfd_base_url}/api/v1/challenges",
        cookies=cookies,
        allow_redirects=False,
    ) as response:
        if response.status == 200 and (json := await response.json())["success"]:
            # Loop through the challenges and get information about each challenge by
            # requesting the `/api/v1/challenges/{challenge_id}` endpoint.
            for challenge_id in [
                challenge["id"]
                for challenge in json["data"]
                if not challenge["solved_by_me"]
            ]:
                async with aiohttp.request(
                    method="get",
                    url=f"{ctfd_base_url}/api/v1/challenges/{challenge_id}",
                    cookies=cookies,
                    allow_redirects=False,
                ) as response:
                    if (
                        response.status == 200
                        and (json := await response.json())["success"]
                    ):
                        challenge = json["data"]
                        yield {
                            "id": challenge["id"],
                            "name": challenge["name"],
                            "value": challenge["value"],
                            "description": challenge["description"],
                            "connection_info": challenge["connection_info"]
                            if "connection_info" in challenge
                            else None,
                            "category": challenge["category"],
                            "tags": challenge["tags"],
                            "files": challenge["files"],
                        }


async def get_scoreboard(ctfd_base_url: str, username: str, password: str) -> list:
    """Get scoreboard from the CTFd platform.

    Args:
        ctfd_base_url: The CTFd platform to login into.
        username: The username to login with.
        password: The password to login with.

    Returns:
        A list of teams sorted by rank in descending order.
    """
    ctfd_base_url = ctfd_base_url.strip("/")

    # Confirm that we're dealing with a CTFd platform.
    if not await is_ctfd_platform(ctfd_base_url):
        return

    cookies = await login(ctfd_base_url, username, password)

    # Get scoreboard.
    async with aiohttp.request(
        method="get",
        url=f"{ctfd_base_url}/api/v1/scoreboard",
        cookies=cookies,
        allow_redirects=False,
    ) as response:
        if response.status == 200 and (json := await response.json())["success"]:
            return [
                {"name": team["name"], "score": team["score"]}
                for team in json["data"][:20]
            ]


async def register_to_ctfd(
    ctfd_base_url: str, username: str, password: str, email: str
) -> dict:
    """Registers an account in the CTFd platform.

    Args:
        ctfd_base_url: The CTFd platform to register into.
        username: The username.
        password: The password.
        email: The email address.

    Returns:
        A dictionary containing either a "success" or "error" key with an explanatory
        message.
    """
    ctfd_base_url = ctfd_base_url.strip("/")
    if not await is_ctfd_platform(ctfd_base_url):
        return {"error": "Platform isn't CTFd"}

    # Get the nonce.
    async with aiohttp.request(
        method="get", url=f"{ctfd_base_url}/register"
    ) as response:
        if response.status != 200:
            return {"error": "Registrations might be closed"}

        cookies = {cookie.key: cookie.value for cookie in response.cookies.values()}
        nonce = BeautifulSoup(await response.text(), "html.parser").find(
            "input", {"id": "nonce"}
        )["value"]

    async with aiohttp.request(
        method="post",
        url=f"{ctfd_base_url}/register",
        data={
            "name": username,
            "email": email,
            "password": password,
            "nonce": nonce,
            "_submit": "Submit",
        },
        cookies=cookies,
        allow_redirects=False,
    ) as response:
        if response.status == 200:
            # User/Email already taken.
            errors = []
            for error in BeautifulSoup(await response.text(), "html.parser").findAll(
                "div", {"role": "alert"}
            ):
                if error.span:
                    errors.append(error.span.text)
            return {"error": "\n".join(errors or ["Registration failure"])}

        elif response.status != 302:
            # Other errors occured.
            return {"error": "Registration failure"}

        # Registration successful, we proceed to create a team.
        # First, get the nonce.
        async with aiohttp.request(
            method="get",
            url=f"{ctfd_base_url}/teams/new",
            cookies=cookies,
        ) as response:
            nonce = BeautifulSoup(await response.text(), "html.parser").find(
                "input", {"id": "nonce"}
            )["value"]

        async with aiohttp.request(
            method="post",
            url=f"{ctfd_base_url}/teams/new",
            data={
                "name": username,
                "password": password,
                "_submit": "Create",
                "nonce": nonce,
            },
            cookies=cookies,
            allow_redirects=False,
        ) as response:
            if response.status == 200:
                # Team name was already taken.
                errors = []
                for error in BeautifulSoup(
                    await response.text(), "html.parser"
                ).findAll("div", {"role": "alert"}):
                    if error.span:
                        errors.append(error.span.text)
                return {"error": "\n".join(errors or ["Team name already taken"])}

            elif response.status != 302:
                # Other errors occured.
                return {"error": "Couldn't create a team"}

            return {"success": "Registration successful"}
