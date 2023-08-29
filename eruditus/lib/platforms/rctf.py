from datetime import datetime
from typing import Any
from typing import Dict
from typing import Generator
from typing import List

import aiohttp

from .abc import ChallengeSolver
from .abc import ChallengeFile
from .abc import Challenge
from .abc import Optional
from .abc import PlatformABC
from .abc import PlatformCTX
from .abc import RegistrationStatus
from .abc import Session
from .abc import SubmittedFlag
from .abc import SubmittedFlagState
from .abc import Team
from ..util import validate_response
from ..util import validate_response_json


def parse_team(data: Dict[str, Any]) -> Team:
    solved_challenges: List[Challenge] = list()
    for challenge in data.get("solves", []):
        solved_challenges.append(
            Challenge(
                id=challenge["id"],
                name=challenge["name"],
                category=challenge.get("category", None),
                value=challenge.get("points", None),
                solves=challenge.get("solves", None),
                # created_at=challenge.get('created_at', None)
            )
        )

    return Team(
        id=data["id"],
        name=data["name"],
        score=data.get("score", None),
        invite_token=data.get("teamToken", None),
        solves=solved_challenges if len(solved_challenges) > 0 else None,
    )


def parse_challenge(data: Dict[str, Any]) -> Challenge:
    files: List[ChallengeFile] = list()
    for file in data.get("files", []):
        files.append(ChallengeFile(url=file["url"], name=file["name"]))

    return Challenge(
        id=str(data["id"]),
        name=data["name"],
        value=int(data.get("points", "0")),
        description=data["description"],
        category=data["category"],
        files=files,
        solves=data["solves"],
    )


def parse_challenge_solver(data: Dict[str, Any]) -> ChallengeSolver:
    return ChallengeSolver(
        solved_at=datetime.fromtimestamp(data.get("createdAt", 0) // 100),
        team=Team(
            id=data.get("userId", "unknown"), name=data.get("userName", "unknown")
        ),
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
            # Validating response
            if not await validate_response(response, "kind", "data"):
                return None

            # Obtaining json response
            response_json: Dict[str, Any] = await response.json()

            # Validating kind
            if response_json["kind"] != "goodLogin":
                return None

            # Saving token
            auth_token = response_json["data"]["authToken"]
            ctx.args["authToken"] = auth_token
            return Session(token=auth_token)

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
            # Validating request
            if not await validate_response_json(response, "data", "kind"):
                return None

            # Obtaining json response
            response_json: Dict[str, Any] = await response.json()

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
            if response_json["kind"] in statuses:
                result.state = statuses[response_json["kind"]]

            # Update `is_first_blood` if state is correct
            await result.update_first_blood(
                ctx,
                cls.get_challenge,
                challenge_id,
                lambda solves: solves <= 1,
                await cls.get_me(ctx),
            )

            # We are done here
            return result

    @classmethod
    async def pull_challenges(
        cls, ctx: PlatformCTX
    ) -> Generator[Challenge, None, None]:
        # Authorizing if needed
        if not await ctx.login(cls.login):
            return

        async with aiohttp.request(
            method="get",
            url=f"{ctx.url_stripped}/api/v1/challs",
            headers=generate_headers(ctx),
        ) as response:
            # Validating request
            if not await validate_response(response, "data", kind="goodChallenges"):
                return

            # Obtaining json response
            response_json: Dict[str, Any] = await response.json()

            # Iterating over challenges and parsing them
            for challenge in response_json["data"]:
                yield parse_challenge(challenge)

    @classmethod
    async def pull_scoreboard(
        cls, ctx: PlatformCTX, max_entries_count: int = 20
    ) -> Generator[Team, None, None]:
        # Authorizing if needed
        if not await ctx.login(cls.login):
            return

        async with aiohttp.request(
            method="get",
            url=f"{ctx.url_stripped}/api/v1/leaderboard/now"
            f"?limit={max_entries_count}&offset=0",
            headers=generate_headers(ctx),
        ) as response:
            # Validating request
            if not await validate_response(response, "data", kind="goodLeaderboard"):
                return

            # Obtaining json response
            response_json: Dict[str, Any] = await response.json()

            # Iterating over challenges and parsing them
            for team in response_json["data"]["leaderboard"][:max_entries_count]:
                yield parse_team(team)

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
            # Validating request
            if not await validate_response(response, "data", kind="goodUserData"):
                return None

            # Obtaining json response
            response_json: Dict[str, Any] = await response.json()

            # Parsing as a team
            return parse_team(response_json.get("data"))

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
            # Validating response
            if not await validate_response(response, "kind", "data"):
                return RegistrationStatus(
                    success=False,
                    message="Got an invalid response from rCTF register endpoint",
                )

            # Obtaining json response
            response_json: Dict[str, Any] = await response.json()

            # Errors lookup
            errors: Dict[str, str] = {
                "badRecaptchaCode": "Unable to solve recaptcha im sorry..",
                "badCtftimeToken": "Invalid ctftime token huh?",
                "badEmail": "Invalid email",
                "badName": "Invalid name",
                "badCompetitionNotAllowed": "Invalid competition huh?",
                "badKnownEmail": "Email already used",
                "badKnownName": "Name already used",
            }

            # Looking up error
            kind: str = response_json["kind"]
            if kind in errors:
                return RegistrationStatus(
                    success=False, message=errors[response_json["kind"]]
                )

            # Building result object
            result = RegistrationStatus(
                success=True, message=response_json.get("message", "No message")
            )
            result.token = response_json.get("data", {}).get("authToken", None)

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
    ) -> Generator[ChallengeSolver, None, None]:
        async with aiohttp.request(
            method="get",
            headers=generate_headers(ctx),
            url=f"{ctx.url_stripped}/api/v1/challs/{challenge_id}/solves"
            f"?limit={limit}&offset=0",
        ) as response:
            # Validating request
            if not await validate_response(
                response, "data", kind="goodChallengeSolves"
            ):
                return

            # Obtaining json response
            response_json: Dict[str, Any] = await response.json()

            # Iterating over challenge solvers and deserializing em
            for solver in response_json["data"].get("solves", []):
                yield parse_challenge_solver(solver)

    @classmethod
    async def get_challenge(
        cls, ctx: PlatformCTX, challenge_id: str, pull_solvers: bool = False
    ) -> Optional[Challenge]:
        # @note: @es3n1n: There's no single challenge getter in rCTF
        # :shrug:

        # A util that would pull solvers if we need them
        async def proceed(result: Challenge) -> Challenge:
            if not pull_solvers:
                return result

            # Pulling solvers if needed
            result.solved_by = [
                x async for x in cls.pull_challenge_solvers(ctx, challenge_id)
            ]
            result.solved_by.sort(key=lambda it: it.solved_at)
            return result

        # Iterating over unsolved challenges
        async for challenge in cls.pull_challenges(ctx):
            # Comparing ids
            if challenge.id != challenge_id:
                continue

            # Yay! Matched
            return await proceed(challenge)

        # Obtaining team object
        cur_team: Team = await cls.get_me(ctx)
        if cur_team is None:
            return None

        # Iterating over solved challenges
        for challenge in cur_team.solves or []:
            # Comparing ids
            if challenge.id != challenge_id:
                continue

            # Yay! Matched
            return await proceed(challenge)

        # No results
        return None
