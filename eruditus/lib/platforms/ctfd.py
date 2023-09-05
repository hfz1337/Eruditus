import io
import re
from datetime import datetime
from logging import getLogger
from typing import AsyncIterator

import aiohttp
from bs4 import BeautifulSoup

from lib.platforms.abc import (
    Challenge,
    ChallengeSolver,
    Optional,
    PlatformABC,
    PlatformCTX,
    RegistrationStatus,
    Retries,
    Session,
    SubmittedFlag,
    SubmittedFlagState,
    Team,
)
from lib.util import deserialize_response, is_empty_string
from lib.validators.ctfd import (
    ChallengeResponse,
    ChallengesResponse,
    MessageResponse,
    ScoreboardResponse,
    SolvesResponse,
    StandingsResponse,
    SubmissionResponse,
    UserResponse,
)

logger = getLogger("eruditus.ctfd")


class CTFd(PlatformABC):
    @classmethod
    async def match_platform(cls, ctx: PlatformCTX) -> bool:
        """Check whether a website is using the CTFd framework.

        Args:
            ctx: Platform context.

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
            ctx: Platform context.

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
    async def fetch(cls, ctx: PlatformCTX, url: str) -> Optional[io.BytesIO]:
        """Fetch a URL endpoint from the CTFd platform and return its response.

        Args:
            ctx: Platform context.
            url: The URL to fetch.

        Returns:
            A file-like object for reading the response data.
        """
        if not await ctx.login(cls.login):
            return None

        if not url.startswith(ctx.base_url):
            return None

        async with aiohttp.request(
            method="get",
            url=url,
            cookies=ctx.session.cookies,
            allow_redirects=False,
        ) as response:
            if response.status != 200:
                return None
            try:
                content = await response.read()
            except aiohttp.ClientError:
                return None
            return io.BytesIO(content)

    @classmethod
    async def submit_flag(
        cls, ctx: PlatformCTX, challenge_id: str, flag: str
    ) -> Optional[SubmittedFlag]:
        """Attempt to submit the flag into the CTFd platform and check if we got first
        blood in case it succeeds.

        Args:
            ctx: Platform context.
            challenge_id: Challenge ID.
            flag: Flag to submit.

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
            # Validating and deserializing response
            data = await deserialize_response(response, model=SubmissionResponse)
            if not data:
                return

            # Parse the number of retries left (for challenges with limited attempts).
            matched = re.match(
                r"Incorrect. You have (?P<tries>\d+) tries remaining.",
                data.data.message,
            )
            tries_left = int(matched.group("tries")) if matched is not None else None

            # Parse the flag state.
            rules: dict[str, SubmittedFlagState] = {
                "paused": SubmittedFlagState.CTF_PAUSED,
                "ratelimited": SubmittedFlagState.RATE_LIMITED,
                "incorrect": SubmittedFlagState.INCORRECT,
                "correct": SubmittedFlagState.CORRECT,
                "already_solved": SubmittedFlagState.ALREADY_SUBMITTED,
            }
            state = rules.get(data.data.status.lower(), SubmittedFlagState.UNKNOWN)

            # Build the result.
            result = SubmittedFlag(
                state=state,
                retries=Retries(left=tries_left) if tries_left is not None else None,
            )

            # Update `is_first_blood` if state is correct.
            await result.update_first_blood(
                ctx,
                cls.pull_challenge_solvers,
                cls.get_challenge,
                challenge_id,
                await cls.get_me(ctx),
            )
            return result

    @classmethod
    async def pull_challenges(cls, ctx: PlatformCTX) -> AsyncIterator[Challenge]:
        """Pull new challenges from the CTFd platform.

        Args:
            ctx: Platform context.

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
            # If there's a message instead of challenges
            msg_response = await deserialize_response(
                response, model=MessageResponse, suppress_warnings=True
            )
            if msg_response:
                logger.warning(
                    'Suppressing challenge getter warnings because of the "%s"',
                    msg_response.message,
                )

            # Validating and deserializing response
            data = await deserialize_response(
                response,
                model=ChallengesResponse,
                suppress_warnings=msg_response is not None,
            )
            if not data:
                return

            # Loop through the challenges and get information about each challenge by
            # requesting the `/api/v1/challenges/{challenge_id}` endpoint.
            for min_challenge in data.data:
                min_challenge_id: str = str(min_challenge.id)

                challenge = await cls.get_challenge(ctx, min_challenge_id)
                if challenge is None:
                    continue

                yield challenge

    @classmethod
    async def pull_scoreboard(
        cls, ctx: PlatformCTX, max_entries_count: int = 20
    ) -> AsyncIterator[Team]:
        """Get scoreboard from the CTFd platform.

        Args:
            ctx: Platform context.
            max_entries_count: Max entries count

        Returns:
            A list of teams sorted by rank in descending order.
        """
        if not await ctx.login(cls.login):
            return

        async with aiohttp.request(
            method="get",
            url=f"{ctx.url_stripped}/api/v1/scoreboard",
            cookies=ctx.session.cookies,
            allow_redirects=False,
        ) as response:
            # Validating and deserializing response
            data = await deserialize_response(response, model=ScoreboardResponse)
            if not data:
                return

            for team in data.data[:max_entries_count]:
                yield team.convert()

    @classmethod
    async def pull_scoreboard_datapoints(
        cls, ctx: PlatformCTX
    ) -> Optional[list[tuple[str, list[datetime], list[int]]]]:
        """Get scoreboard data points for the top teams.

        Args:
            ctx: Platform context.

        Returns:
            A list where each element is a tuple containing:
                - The team name (used as the label in the graph).
                - The timestamps of each solve (as `datetime` objects, these will fill
                  x axis).
                - The change in the number of points (these will add to form the y axis
                  values).
        """
        if not await ctx.login(cls.login):
            return

        async with aiohttp.request(
            method="get",
            url=f"{ctx.url_stripped}/api/v1/scoreboard/top/10",
            cookies=ctx.session.cookies,
            allow_redirects=False,
        ) as response:
            # Validating and deserializing response
            data = await deserialize_response(response, model=StandingsResponse)
            if not data or not data.data:
                return

            graphs = []
            for standing in data.data.values():
                score = 0
                team = standing.name
                x = []
                y = []
                for solve in standing.solves:
                    score += solve.value
                    x.append(datetime.strptime(solve.date, "%Y-%m-%dT%H:%M:%S.%fZ"))
                    y.append(score)
                graphs.append((team, x, y))

            return graphs

    @classmethod
    async def register(cls, ctx: PlatformCTX) -> RegistrationStatus:
        """Registers an account in the CTFd platform.

        Args:
            ctx: Platform context.

        Returns:
            A dictionary containing either a "success" or "error" key with an
            explanatory message.
        """
        # Assert registration data
        if any(
            is_empty_string(ctx.args.get(value))
            for value in ("username", "email", "password")
        ):
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
            ) as teams_resp:
                nonce = BeautifulSoup(await teams_resp.text(), "html.parser").find(
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
            ) as teams_resp:
                if teams_resp.status == 200:
                    # Team name was already taken.
                    errors = []
                    for error in BeautifulSoup(
                        await teams_resp.text(), "html.parser"
                    ).findAll("div", {"role": "alert"}):
                        if error.span:
                            errors.append(error.span.text)

                    return RegistrationStatus(
                        success=False,
                        message="\n".join(errors or ["Team name already taken"]),
                    )

                elif teams_resp.status != 302:
                    # Other errors occurred.
                    return RegistrationStatus(
                        success=False, message="Couldn't create a team"
                    )

                return RegistrationStatus(success=True)

    @classmethod
    async def pull_challenge_solvers(
        cls, ctx: PlatformCTX, challenge_id: str, limit: int = 10
    ) -> AsyncIterator[ChallengeSolver]:
        if not await ctx.login(cls.login):
            return

        async with aiohttp.request(
            method="get",
            url=f"{ctx.base_url}/api/v1/challenges/{challenge_id}/solves",
            cookies=ctx.session.cookies,
            allow_redirects=False,
        ) as response:
            # Validating and deserializing response
            data = await deserialize_response(response, model=SolvesResponse)
            if not data:
                return

            for solver in data.data[: limit if limit != 0 else len(data.data)]:
                yield solver.convert()

    @classmethod
    async def get_challenge(
        cls, ctx: PlatformCTX, challenge_id: str
    ) -> Optional[Challenge]:
        """Get a challenge by its ID.

        Args:
            ctx: Platform context.
            challenge_id: Numerical challenge ID.

        Returns:
            Parsed challenge.
        """
        if not await ctx.login(cls.login):
            return None

        async with aiohttp.request(
            method="get",
            url=f"{ctx.base_url}/api/v1/challenges/{challenge_id}",
            cookies=ctx.session.cookies,
            allow_redirects=False,
        ) as response:
            # Validating and deserializing response
            data = await deserialize_response(response, model=ChallengeResponse)
            if not data:
                return

            return data.data.convert(ctx.url_stripped)

    @classmethod
    async def get_me(cls, ctx: PlatformCTX) -> Optional[Team]:
        """Get our team info.

        Args:
            ctx: Platform context.

        Returns:
            Parsed team info.
        """
        if not await ctx.login(cls.login):
            return None

        async with aiohttp.request(
            method="get",
            url=f"{ctx.base_url}/api/v1/teams/me",
            cookies=ctx.session.cookies,
            allow_redirects=False,
        ) as response:
            # Validating and deserializing response
            data = await deserialize_response(response, model=UserResponse)
            if not data:
                return

            return data.data.convert()
