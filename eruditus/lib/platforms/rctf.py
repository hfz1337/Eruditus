import io
from datetime import datetime
from typing import AsyncIterator

import aiohttp

from lib.platforms.abc import (
    Challenge,
    ChallengeSolver,
    Optional,
    PlatformABC,
    PlatformCTX,
    RegistrationStatus,
    Session,
    SubmittedFlag,
    SubmittedFlagState,
    Team,
)
from lib.util import deserialize_response, is_empty_string
from lib.validators.rctf import (
    AuthResponse,
    ChallengesReponse,
    LeaderboardResponse,
    SolvesResponse,
    StandingsResponse,
    SubmissionResponse,
    UserResponse,
)


def generate_headers(ctx: PlatformCTX) -> dict[str, str]:
    if not ctx.session or not ctx.session.validate():
        return {}

    return {"Authorization": f'Bearer {ctx.args["authToken"]}'}


class RCTF(PlatformABC):
    @classmethod
    async def match_platform(cls, ctx: PlatformCTX) -> bool:
        """Check whether a website is using the rCTF framework.

        Args:
            ctx: Platform context.

        Returns:
            True if the platform is using rCTF, else False.
        """
        async with aiohttp.request(
            method="get",
            url=f"{ctx.url_stripped}/api/v1/leaderboard/now?limit=0&offset=0",
        ) as response:
            _text: str = await response.text()

            return "badNotStarted" in _text or "goodLeaderboard" in _text

    @classmethod
    async def login(cls, ctx: PlatformCTX) -> Optional[Session]:
        if ctx.is_authorized():
            return ctx.session

        # Send authentication request
        async with aiohttp.request(
            method="post",
            url=f"{ctx.url_stripped}/api/v1/auth/login",
            json={
                "teamToken": ctx.args.get("teamToken"),
            },
            allow_redirects=False,
        ) as response:
            # Validate and deserialize response
            data = await deserialize_response(response, model=AuthResponse)
            if not data or data.is_not_good():
                return None

            # Save the token
            ctx.args["authToken"] = data.data.authToken
            return Session(token=data.data.authToken)

    @classmethod
    async def fetch(cls, ctx: PlatformCTX, url: str) -> Optional[io.BytesIO]:
        """Fetch a URL endpoint from the rCTF platform and return its response.

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
            headers=generate_headers(ctx),
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
        # Authorize if needed
        if not await ctx.login(cls.login):
            return None

        # Send submission request
        async with aiohttp.request(
            method="post",
            url=f"{ctx.url_stripped}/api/v1/challs/{challenge_id}/submit",
            json={"flag": flag},
            headers=generate_headers(ctx),
        ) as response:
            # Validate and deserialize response
            data = await deserialize_response(response, model=SubmissionResponse)
            if not data:
                return

            # Initialize result
            result: SubmittedFlag = SubmittedFlag(state=SubmittedFlagState.UNKNOWN)

            # Lookup table for flag submission states
            statuses: dict[str, SubmittedFlagState] = {
                "goodFlag": SubmittedFlagState.CORRECT,
                "badNotStarted": SubmittedFlagState.CTF_NOT_STARTED,
                "badEnded": SubmittedFlagState.CTF_ENDED,
                "badChallenge": SubmittedFlagState.INVALID_CHALLENGE,
                "badRateLimit": SubmittedFlagState.RATE_LIMITED,
                "badFlag": SubmittedFlagState.INCORRECT,
                "badAlreadySolvedChallenge": SubmittedFlagState.ALREADY_SUBMITTED,
                "badUnknownUser": SubmittedFlagState.INVALID_USER,
            }

            # Resolve kind to status
            if data.kind in statuses:
                result.state = statuses[data.kind]

            # Update `is_first_blood` if state is correct
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
        # Authorize if needed
        if not await ctx.login(cls.login):
            return

        async with aiohttp.request(
            method="get",
            url=f"{ctx.url_stripped}/api/v1/challs",
            headers=generate_headers(ctx),
        ) as response:
            # Validate and deserialize response
            data = await deserialize_response(response, model=ChallengesReponse)
            if not data or data.is_not_good() or not data.data:
                return

            # Iterate over challenges and parse them
            for challenge in data.data:
                yield challenge.convert(ctx.url_stripped)

    @classmethod
    async def pull_scoreboard(
        cls, ctx: PlatformCTX, max_entries_count: int = 20
    ) -> AsyncIterator[Team]:
        # Authorize if needed
        if not await ctx.login(cls.login):
            return

        async with aiohttp.request(
            method="get",
            url=f"{ctx.url_stripped}/api/v1/leaderboard/now",
            params={"limit": str(max_entries_count), "offset": "0"},
            headers=generate_headers(ctx),
        ) as response:
            # Validate and deserialize response
            data = await deserialize_response(response, model=LeaderboardResponse)
            if not data or data.is_not_good() or not data.data:
                return

            # Iterate over teams and parse them
            for team in data.data.leaderboard[:max_entries_count]:
                yield team.convert(ctx.url_stripped)

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
                  the x axis).
                - The number of accumulated points after each new solve (these will
                  fill the y axis).
        """
        if not await ctx.login(cls.login):
            return

        async with aiohttp.request(
            method="get",
            url=f"{ctx.url_stripped}/api/v1/leaderboard/graph",
            params={"limit": 10, "offset": "0"},
            headers=generate_headers(ctx),
        ) as response:
            # Validating and deserializing response
            data = await deserialize_response(response, model=StandingsResponse)
            if not data or not data.data.graph:
                return

            graphs = []
            for standing in data.data.graph:
                team = standing.name
                x = []
                y = []
                for solve in standing.points:
                    x.append(datetime.fromtimestamp(solve.time // 1e3))
                    y.append(solve.score)
                graphs.append((team, x, y))

            return graphs

    @classmethod
    async def get_me(cls, ctx: PlatformCTX) -> Optional[Team]:
        # Authorize if needed
        if not await ctx.login(cls.login):
            return None

        async with aiohttp.request(
            method="get",
            url=f"{ctx.url_stripped}/api/v1/users/me",
            headers=generate_headers(ctx),
        ) as response:
            # Validate and deserialize response
            data = await deserialize_response(response, model=UserResponse)
            if not data or data.is_not_good():
                return

            # Parse as a team
            return data.data.convert(ctx.url_stripped)

    @classmethod
    async def register(cls, ctx: PlatformCTX) -> RegistrationStatus:
        # Assert registration data
        ctx.args["team"] = ctx.args.get("team") or ctx.args.get("username")
        if any(is_empty_string(ctx.args.get(value)) for value in ("team", "email")):
            return RegistrationStatus(
                success=False, message="Not enough values in context"
            )

        # Send registration request
        async with aiohttp.request(
            method="post",
            url=f"{ctx.url_stripped}/api/v1/auth/register",
            json={
                "name": ctx.args.get("team"),
                "email": ctx.args.get("email"),
            },
            allow_redirects=False,
        ) as response:
            # Validate and deserialize response
            data = await deserialize_response(response, model=AuthResponse)
            if not data:
                return RegistrationStatus(
                    success=False,
                    message="Got an invalid response from rCTF register endpoint",
                )

            # If something went wrong
            if data.is_not_good() or not data.data or not data.data.authToken:
                return RegistrationStatus(success=False, message=data.message)

            # Build the result object
            result = RegistrationStatus(success=True, message=data.message)
            result.token = data.data.authToken

            # Build the session
            ctx.session = Session(token=result.token)
            ctx.args["authToken"] = result.token

            # We are gucci if there's a token in the result
            result.success = not is_empty_string(result.token)

            # If something's off
            if not result.success:
                return result

            # Obtain our team's object
            our_team: Optional[Team] = await cls.get_me(ctx)
            if not our_team:
                result.success = False
                result.message = "Couldn't retrieve our team information"
                return result

            # Save the token
            result.invite = our_team.invite_token

            return result

    @classmethod
    async def pull_challenge_solvers(
        cls, ctx: PlatformCTX, challenge_id: str, limit: int = 10
    ) -> AsyncIterator[ChallengeSolver]:
        async with aiohttp.request(
            method="get",
            url=f"{ctx.url_stripped}/api/v1/challs/{challenge_id}/solves",
            params={"limit": str(limit), "offset": "0"},
            headers=generate_headers(ctx),
        ) as response:
            # Validate and deserialize response
            data = await deserialize_response(response, model=SolvesResponse)
            if not data or data.is_not_good():
                return

            # Iterate over challenge solvers and deserialize them
            for solver in data.data.solves:
                yield solver.convert()

    @classmethod
    async def get_challenge(
        cls, ctx: PlatformCTX, challenge_id: str
    ) -> Optional[Challenge]:
        """Retrieve a challenge from the rCTF platform.

        Args:
            ctx: Platform context.
            challenge_id: Challenge identifier.

        Returns:
            Parsed challenge.

        Notes:
            Because rCTF doesn't have an API endpoint for fetching a single challenge
            at a time, we need to request all challenges using the `/api/v1/challs`
            endpoint and loop through them in order to fetch a specific challenge.
        """

        # Iterate over unsolved challenges
        async for challenge in cls.pull_challenges(ctx):
            # Compare challenge IDs
            if challenge.id != challenge_id:
                continue

            return challenge

        # Obtain our team object
        our_team: Team = await cls.get_me(ctx)
        if our_team is None:
            return None

        # Iterate over solved challenges
        for challenge in our_team.solves or []:
            # Compare challenge IDs
            if challenge.id != challenge_id:
                continue

            return challenge

        return None
