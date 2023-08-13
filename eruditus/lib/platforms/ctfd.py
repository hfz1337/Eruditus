import re
from typing import Any
from typing import Dict
from typing import Generator
from typing import List

import aiohttp
from bs4 import BeautifulSoup

from .abc import Challenge
from .abc import ChallengeFile
from .abc import Optional
from .abc import PlatformABC
from .abc import PlatformCTX
from .abc import RegistrationStatus
from .abc import Retries
from .abc import Session
from .abc import SubmittedFlag
from .abc import SubmittedFlagState
from .abc import Team
from ..util import validate_response


def parse_team(data: Dict[str, Any]) -> Team:
    return Team(name=data["name"], score=data["score"] if "score" in data else None)


def parse_challenge(data: Dict[str, Any], ctx: PlatformCTX) -> Challenge:
    files: List[ChallengeFile] = list()
    for file in data.get("files", []):
        files.append(ChallengeFile(url=f"{ctx.url_stripped}/{file}", name=None))

    return Challenge(
        id=str(data.get("id")),
        name=data.get("name"),
        value=int(data.get("value")),
        description=data.get("description"),
        connection_info=data.get("connection_info"),
        category=data.get("category"),
        tags=data.get("tags"),
        files=files,
        solves=data.get("solves"),
    )


class CTFd(PlatformABC):
    @classmethod
    async def match_platform(cls, ctx: PlatformCTX) -> bool:
        """Check whether a website is using the CTFd framework.

        Args:
            ctx: Context

        Returns:
            True if the platform is using CTFd, else False.
        """
        async with aiohttp.request(
            method="get",
            url=f"{ctx.url_stripped}/plugins/challenges/assets/view.js",
        ) as response:
            return "CTFd" in await response.text()

    @classmethod
    async def login(cls, ctx: PlatformCTX) -> Optional[Session]:
        """Login to the CTFd platform.

        Args:
            ctx: Context

        Returns:
            A session object
        """
        if ctx.session and len(ctx.session.cookies) > 0:
            return ctx.session

        ctfd_base_url = ctx.url_stripped

        # Get the nonce.
        async with aiohttp.request(
            method="get", url=f"{ctfd_base_url}/login"
        ) as response:
            cookies = {cookie.key: cookie.value for cookie in response.cookies.values()}
            nonce = BeautifulSoup(await response.text(), "html.parser").find(
                "input", {"id": "nonce"}
            )

            if nonce is None:
                return None
            nonce = nonce["value"]

        # Login to CTFd.
        data = {
            "name": ctx.args.get("username"),
            "password": ctx.args.get("password"),
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
            cookies = {cookie.key: cookie.value for cookie in response.cookies.values()}

            ctx.session = Session(cookies=cookies)
            return ctx.session

    @classmethod
    async def submit_flag(
        cls, ctx: PlatformCTX, challenge_id: str, flag: str
    ) -> Optional[SubmittedFlag]:
        """Attempt to submit the flag into the CTFd platform and check if we got first
        blood in case it succeeds.

        Args:
            ctx: Context
            challenge_id: Challenge id
            flag: Flag of the challenge.

        Returns:
            A SubmittedFlag object containing the status message and a boolean
            indicating if we got first blood.
        """
        if not await ctx.login(cls.login):
            return

        ctfd_base_url = ctx.url_stripped

        # Get CSRF token.
        async with aiohttp.request(
            method="get", url=f"{ctfd_base_url}/challenges", cookies=ctx.session.cookies
        ) as response:
            csrf_nonce = re.search(
                '(?<=csrfNonce\': ")[A-Fa-f0-9]+(?=")', await response.text()
            )

        if csrf_nonce is None:
            return None

        csrf_nonce = csrf_nonce.group(0)
        json = {"challenge_id": int(challenge_id), "submission": flag}

        async with aiohttp.request(
            method="post",
            url=f"{ctfd_base_url}/api/v1/challenges/attempt",
            json=json,
            cookies=ctx.session.cookies,
            headers={"CSRF-Token": csrf_nonce},
        ) as response:
            # Validating response
            if not await validate_response(response, success=True, data=["status"]):
                return None

            # Obtaining json
            response_json: Dict[str, Any] = await response.json()

            # Parsing retries left from the message
            def parse_retries() -> Optional[Retries]:
                # No message? huh?
                if "message" not in response_json["data"]:
                    return None

                # Trying to match the message
                # @ref:
                # https://github.com/CTFd/CTFd/blob/master/CTFd/api/v1/challenges.py#L672
                message: str = response_json["data"]["message"]
                if "You have" not in message or "remaining." not in message:
                    return None

                # Split the message
                # @todo: @es3n1n: add regex
                arguments: List[str] = message.split("You have", maxsplit=1)
                if len(arguments) != 2:
                    return None

                # Extracting the digit from this mess
                # @fixme: @es3n1n: add regex
                retries_left_str: str = arguments[1].strip().split(" ")[0].strip()
                if not retries_left_str.isdigit():
                    return None

                # Yay
                return Retries(left=int(retries_left_str))

            # Matching flag state
            def parse_flag_state() -> SubmittedFlagState:
                # Obtaining the status str
                status_str = str(response_json["data"]["status"]).lower()

                # Lookup rules
                rules: Dict[str, SubmittedFlagState] = {
                    "paused".lower(): SubmittedFlagState.CTF_PAUSED,
                    "ratelimited".lower(): SubmittedFlagState.RATE_LIMITED,
                    "incorrect".lower(): SubmittedFlagState.INCORRECT,
                    "correct".lower(): SubmittedFlagState.CORRECT,
                }

                # Unknown state O_o
                if status_str not in rules:
                    return SubmittedFlagState.UNKNOWN

                return rules[status_str]

            # Building result
            result = SubmittedFlag(state=parse_flag_state(), retries=parse_retries())

            # Update `is_first_blood` if state is correct
            await result.update_first_blood(
                ctx, cls.get_challenge, challenge_id, lambda x: x <= 1
            )

            # We are done here
            return result

    @classmethod
    async def pull_challenges(
        cls, ctx: PlatformCTX
    ) -> Generator[Challenge, None, None]:
        """Pull new challenges from the CTFd platform.

        Args:
            ctx: Context

        Yields:
            A dictionary representing information about the challenge.
        """
        if not await ctx.login(cls.login):
            return

        # Get challenges.
        async with aiohttp.request(
            method="get",
            url=f"{ctx.url_stripped}/api/v1/challenges",
            cookies=ctx.session.cookies,
            allow_redirects=False,
        ) as response:
            if not await validate_response(response, "data", success=True):
                return

            # Obtaining json
            response_json: Dict[str, Any] = await response.json()

            # Loop through the challenges and get information about each challenge by
            # requesting the `/api/v1/challenges/{challenge_id}` endpoint.
            for min_challenge in response_json["data"]:
                min_challenge_id: str = str(min_challenge["id"])

                challenge = await cls.get_challenge(ctx, min_challenge_id)
                if challenge is None:
                    continue

                yield challenge

    @classmethod
    async def pull_scoreboard(
        cls, ctx: PlatformCTX, max_entries_count: int = 20
    ) -> Generator[Team, None, None]:
        """Get scoreboard from the CTFd platform.

        Args:
            ctx: Context data
            max_entries_count: Max entries count

        Returns:
            A list of teams sorted by rank in descending order.
        """
        if not await ctx.login(cls.login):
            return

        # Get scoreboard.
        async with aiohttp.request(
            method="get",
            url=f"{ctx.url_stripped}/api/v1/scoreboard",
            cookies=ctx.session.cookies,
            allow_redirects=False,
        ) as response:
            # Validating response
            if not await validate_response(response, success=True):
                return

            # Obtaining json
            response_json: Dict[str, Any] = await response.json()

            for team in response_json["data"][:max_entries_count]:
                yield parse_team(team)

    @classmethod
    async def register(cls, ctx: PlatformCTX) -> RegistrationStatus:
        """Registers an account in the CTFd platform.

        Args:
            ctx: Context

        Returns:
            A dictionary containing either a "success" or "error"
             key with an explanatory message.
        """
        # Assert registration data
        needed_values = ["username", "email", "password"]

        for needed_value in needed_values:
            if not ctx.validate_arg(needed_value, None, "", " "):
                return RegistrationStatus(
                    success=False, message="Not enough values in context"
                )

        # Get the nonce.
        async with aiohttp.request(
            method="get", url=f"{ctx.url_stripped}/register"
        ) as response:
            if response.status != 200:
                return RegistrationStatus(
                    success=False, message="Registration might be closed"
                )

            cookies = {cookie.key: cookie.value for cookie in response.cookies.values()}
            nonce = BeautifulSoup(await response.text(), "html.parser").find(
                "input", {"id": "nonce"}
            )["value"]

        async with aiohttp.request(
            method="post",
            url=f"{ctx.url_stripped}/register",
            data={
                "name": ctx.args.get("username"),
                "email": ctx.args.get("email"),
                "password": ctx.args.get("password"),
                "nonce": nonce,
                "_submit": "Submit",
            },
            cookies=cookies,
            allow_redirects=False,
        ) as response:
            if response.status == 200:
                # User/Email already taken.
                errors = []
                for error in BeautifulSoup(
                    await response.text(), "html.parser"
                ).findAll("div", {"role": "alert"}):
                    if error.span:
                        errors.append(error.span.text)

                return RegistrationStatus(
                    success=False, message="\n".join(errors or ["Registration failure"])
                )

            if response.status != 302:
                # Other errors occurred.
                return RegistrationStatus(success=False, message="Registration failure")

            # Registration successful, we proceed to create a team.
            # First, get the nonce.
            async with aiohttp.request(
                method="get",
                url=f"{ctx.url_stripped}/teams/new",
                cookies=cookies,
            ) as response:
                nonce = BeautifulSoup(await response.text(), "html.parser").find(
                    "input", {"id": "nonce"}
                )["value"]

            async with aiohttp.request(
                method="post",
                url=f"{ctx.url_stripped}/teams/new",
                data={
                    "name": ctx.args.get("username"),
                    "password": ctx.args.get("password"),
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

                    return RegistrationStatus(
                        success=False,
                        message="\n".join(errors or ["Team name already taken"]),
                    )

                elif response.status != 302:
                    # Other errors occurred.
                    return RegistrationStatus(
                        success=False, message="Couldn't create a team"
                    )

                return RegistrationStatus(success=True)

    @classmethod
    async def get_challenge(
        cls, ctx: PlatformCTX, challenge_id: str
    ) -> Optional[Challenge]:
        """Get challenge by its id

        ctx: Context
        challenge_id: ID

        Returns parsed Challenge
        """
        if not await ctx.login(cls.login):
            return None

        async with aiohttp.request(
            method="get",
            url=f"{ctx.base_url}/api/v1/challenges/{challenge_id}",
            cookies=ctx.session.cookies,
            allow_redirects=False,
        ) as response:
            # Validating response
            if not await validate_response(response, success=True, data=["id"]):
                return None

            response_json: Dict[str, Any] = await response.json()
            return parse_challenge(response_json["data"], ctx)
