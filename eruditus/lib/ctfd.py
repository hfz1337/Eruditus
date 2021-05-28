from typing import Tuple, Generator
import re
import requests
from bs4 import BeautifulSoup


def is_ctfd_platform(ctfd_base_url: str) -> bool:
    """Checks whether a website is using the CTFd framework.

    Args:
        ctfd_base_url: URL of the CTF platform to check for.

    Returns:
        True if the platform is using CTFd, else False.

    """
    ctfd_signature = "Powered by CTFd"
    response = requests.get(url=f"{ctfd_base_url.strip()}/")
    return ctfd_signature in response.text


def login(ctfd_base_url: str, username: str, password: str) -> dict:
    """Logins to the CTFd platform.

    Args:
        ctfd_base_url: The CTFd platform to login into.
        username: The username to login with.
        password: The password to login with.

    Returns:
        A dictionary containing session cookies.

    """
    ctfd_base_url = ctfd_base_url.strip("/")

    # Confirm that we're dealing with a CTFd platform
    if not is_ctfd_platform(ctfd_base_url):
        return None

    # Get the nonce
    response = requests.get(url=f"{ctfd_base_url}/login")
    cookies = response.cookies.get_dict()
    nonce = BeautifulSoup(response.content, "html.parser").find(
        "input", {"id": "nonce"}
    )["value"]

    # Login to CTFd
    data = {"name": username, "password": password, "_submit": "Submit", "nonce": nonce}
    response = requests.post(
        url=f"{ctfd_base_url}/login", data=data, cookies=cookies, allow_redirects=False
    )
    return response.cookies.get_dict()


def submit_flag(
    ctfd_base_url: str, username: str, password: str, challenge_id: int, flag: str
) -> Tuple[str, bool]:
    """Attempts to submit the flag into the CTFd platform and checks if we got first
    blood in case it succeeds.

    Args:
        ctfd_base_url: The CTFd platform to login into.
        username: The username to login with.
        password: The password to login with.
        challenge_id: ID of the challenge to the submit the flag for.
        flag: Flag of the challenge.

    Returns:
        a tuple containing the status message and a boolean indicating if we got
        first blood.
    """
    ctfd_base_url = ctfd_base_url.strip("/")
    cookies = login(ctfd_base_url, username, password)
    if cookies is None:
        return (None, None)

    # Get CSRF token
    response = requests.get(url=f"{ctfd_base_url}/challenges", cookies=cookies)
    csrf_nonce = re.search('(?<=csrfNonce\': ")[A-Fa-f0-9]+(?=")', response.text)
    if csrf_nonce is None:
        return (None, None)

    csrf_nonce = csrf_nonce.group(0)
    json = {"challenge_id": challenge_id, "submission": flag}
    response = requests.post(
        url=f"{ctfd_base_url}/api/v1/challenges/attempt",
        json=json,
        cookies=cookies,
        headers={"CSRF-Token": csrf_nonce},
    )
    # Check if we got a response
    if response.status_code == 200 and response.json()["success"]:
        # The flag was correct
        if response.json()["data"]["status"] == "correct":
            # Check if we got first blood
            response = requests.get(
                url=f"{ctfd_base_url}/api/v1/challenges/{challenge_id}",
                cookies=cookies,
                allow_redirects=False,
            )
            if response.status_code == 200 and response.json()["success"]:
                return ("correct", response.json()["data"]["solves"] == 1)

            return ("correct", None)
        # We already solved this challenge, or the flag was incorrect
        return (response.json()["data"]["status"], None)

    return (None, None)


def pull_challenges(
    ctfd_base_url: str, username: str, password: str
) -> Generator[dict, None, None]:
    """Pull new challenges from the CTFd platform.

    Args:
        ctfd_base_url: The CTFd platform to login into.
        username: The username to login with.
        password: The password to login with.

    Yields:
        dict: Information about the challenge.

    """
    ctfd_base_url = ctfd_base_url.strip("/")

    # Confirm that we're dealing with a CTFd platform
    if not is_ctfd_platform(ctfd_base_url):
        return None

    # Maybe the challenges endpoint is accessible to the public?
    response = requests.get(
        url=f"{ctfd_base_url}/api/v1/challenges", allow_redirects=False
    )

    if response.status_code != 200:
        # Perhaps the API access needs authentication, so we login to the CTFd platform.
        cookies = login(ctfd_base_url, username, password)

        # Get challenges
        response = requests.get(
            url=f"{ctfd_base_url}/api/v1/challenges",
            cookies=cookies,
            allow_redirects=False,
        )

    if response.status_code == 200 and response.json()["success"]:
        # Loop through the challenges and get information about each challenge by
        # requesting the `/api/v1/challenges/{challenge_id}` endpoint
        for challenge_id in [
            challenge["id"]
            for challenge in response.json()["data"]
            if not challenge["solved_by_me"]
        ]:
            response = requests.get(
                url=f"{ctfd_base_url}/api/v1/challenges/{challenge_id}",
                cookies=cookies,
                allow_redirects=False,
            )
            if response.status_code == 200 and response.json()["success"]:
                challenge = response.json()["data"]
                yield {
                    "id": challenge["id"],
                    "name": challenge["name"],
                    "value": challenge["value"],
                    "description": challenge["description"],
                    "category": challenge["category"],
                    "tags": challenge["tags"],
                    "files": challenge["files"],
                }
