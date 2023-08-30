from typing import AsyncIterator, Dict

import aiohttp

from ..util import deserialize_response
from ..validators.rctf import (
    AuthResponse,
    ChallengesReponse,
    LeaderboardResponse,
    SolvesResponse,
    SubmissionResponse,
    UserResponse,
)
from .abc import (
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


def generate_headers(ctx: PlatformCTX) -> Dict[str, str]:
    if not ctx.session or not ctx.session.validate():
        return {}

    return {"Authorization": f'Bearer {ctx.args["authToken"]}'}


class RCTF(PlatformABC):
    @classmethod
    async def match_platform(cls, ctx: PlatformCTX) -> bool:
        # Sending test api req
        async with aiohttp.request(
            method="get",
            url=f"{ctx.url_stripped}/api/v1/leaderboard/now?limit=0&offset=0",
        ) as response:
            _text: str = await response.text()

            return "badNotStarted" in _text or "goodLeaderboard" in _text

    @classmethod
    async def login(cls, ctx: PlatformCTX) -> Optional[Session]:
        # Already authorized :shrug:
        if ctx.is_authorized():
            return ctx.session

        # Sending auth request
        async with aiohttp.request(
            method="post",
            url=f"{ctx.url_stripped}/api/v1/auth/login",
            json={
                "teamToken": ctx.args.get("teamToken"),
            },
            allow_redirects=False,
        ) as response:
            # Validating and deserializing response
            data = await deserialize_response(response, model=AuthResponse)
            if not data or data.is_not_good():
                return None

            # Saving the token
            ctx.args["authToken"] = data.data.authToken
            return Session(token=data.data.authToken)

    @classmethod
    async def submit_flag(
        cls, ctx: PlatformCTX, challenge_id: str, flag: str
    ) -> Optional[SubmittedFlag]:
        # Authorizing if needed
        if not await ctx.login(cls.login):
            return None

        # Sending submit request
        async with aiohttp.request(
            method="post",
            url=f"{ctx.url_stripped}/api/v1/challs/{challenge_id}/submit",
            json={"flag": flag},
            headers=generate_headers(ctx),
        ) as response:
            # Validating and deserializing response
            data = await deserialize_response(response, model=SubmissionResponse)
            if not data:
                return

            # Initializing result
            result: SubmittedFlag = SubmittedFlag(state=SubmittedFlagState.UNKNOWN)

            # Lookup table
            statuses: Dict[str, SubmittedFlagState] = {
                "goodFlag": SubmittedFlagState.CORRECT,
                "badNotStarted": SubmittedFlagState.CTF_NOT_STARTED,
                "badEnded": SubmittedFlagState.CTF_ENDED,
                "badChallenge": SubmittedFlagState.INVALID_CHALLENGE,
                "badRateLimit": SubmittedFlagState.RATE_LIMITED,
                "badFlag": SubmittedFlagState.INCORRECT,
                "badAlreadySolvedChallenge": SubmittedFlagState.ALREADY_SUBMITTED,
                "badUnknownUser": SubmittedFlagState.INVALID_USER,
            }

            # Resolving kind to status
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

            # We are done here
            return result

    @classmethod
    async def pull_challenges(cls, ctx: PlatformCTX) -> AsyncIterator[Challenge]:
        # Authorizing if needed
        if not await ctx.login(cls.login):
            return

        async with aiohttp.request(
            method="get",
            url=f"{ctx.url_stripped}/api/v1/challs",
            headers=generate_headers(ctx),
        ) as response:
            # Validating and deserializing response
            data = await deserialize_response(response, model=ChallengesReponse)
            if not data or data.is_not_good():
                return

            # Iterating over challenges and parsing them
            for challenge in data.data:
                yield challenge.convert()

    @classmethod
    async def pull_scoreboard(
        cls, ctx: PlatformCTX, max_entries_count: int = 20
    ) -> AsyncIterator[Team]:
        # Authorizing if needed
        if not await ctx.login(cls.login):
            return

        async with aiohttp.request(
            method="get",
            url=f"{ctx.url_stripped}/api/v1/leaderboard/now",
            params={"limit": str(max_entries_count), "offset": "0"},
            headers=generate_headers(ctx),
        ) as response:
            # Validating and deserializing response
            data = await deserialize_response(response, model=LeaderboardResponse)
            if not data or data.is_not_good():
                return

            # Iterating over challenges and parsing them
            for team in data.data.leaderboard[:max_entries_count]:
                yield team.convert()

    @classmethod
    async def get_me(cls, ctx: PlatformCTX) -> Optional[Team]:
        # Authorizing if needed
        if not await ctx.login(cls.login):
            return None

        async with aiohttp.request(
            method="get",
            url=f"{ctx.url_stripped}/api/v1/users/me",
            headers=generate_headers(ctx),
        ) as response:
            # Validating and deserializing response
            data = await deserialize_response(response, model=UserResponse)
            if not data or data.is_not_good():
                return

            # Parsing as a team
            return data.data.convert()

    @classmethod
    async def register(cls, ctx: PlatformCTX) -> RegistrationStatus:
        # Sending register request
        async with aiohttp.request(
            method="post",
            url=f"{ctx.url_stripped}/api/v1/auth/register",
            json={
                "name": ctx.args.get("username"),
                "email": ctx.args.get("email"),
            },
            allow_redirects=False,
        ) as response:
            # Validating and deserializing response
            data = await deserialize_response(response, model=AuthResponse)
            if not data:
                return RegistrationStatus(
                    success=False,
                    message="Got an invalid response from rCTF register endpoint",
                )

            # If something went wrong
            if data.is_not_good():
                return RegistrationStatus(success=False, message=data.message)

            # Building result object
            result = RegistrationStatus(success=True, message=data.message)
            result.token = data.data.authToken

            # Building session
            ctx.session = Session(token=result.token)
            ctx.args["authToken"] = result.token

            # We are gucci if there's token in the result
            result.success = result.token not in ["", " ", None]

            # If something's off
            if not result.success:
                return result

            # Obtaining our team's object
            our_team: Optional[Team] = await cls.get_me(ctx)

            # No team?
            if not our_team:
                result.success = False
                result.message = "No team object huh?"
                return result

            # Saving the token
            result.invite = our_team.invite_token

            # We are done here
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
            # Validating and deserializing response
            data = await deserialize_response(response, model=SolvesResponse)
            if not data or data.is_not_good():
                return

            # Iterating over challenge solvers and deserializing em
            for solver in data.data.solves:
                yield solver.convert()

    @classmethod
    async def get_challenge(
        cls, ctx: PlatformCTX, challenge_id: str
    ) -> Optional[Challenge]:
        """Retrieve a challenge from the rCTF platform.

        Args:
            ctx: Platform context.
            challenge_id: Challenge identification.

        Returns:
            Parsed challenge.

        Notes:
            Because rCTF doesn't have an API endpoint for fetching a single challenge
            at a time, we need to request all challenges using the `/api/v1/challs`
            endpoint and loop through them in order to fetch a specific challenge.
        """

        # Iterating over unsolved challenges
        async for challenge in cls.pull_challenges(ctx):
            # Comparing ids
            if challenge.id != challenge_id:
                continue

            # Yay! Matched
            return challenge

        # Obtaining a team object
        cur_team: Team = await cls.get_me(ctx)
        if cur_team is None:
            return None

        # Iterating over solved challenges
        for challenge in cur_team.solves or []:
            # Comparing ids
            if challenge.id != challenge_id:
                continue

            # Yay! Matched
            return challenge

        # No results
        return None
