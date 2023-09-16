from enum import Enum, EnumMeta
from typing import Optional

import aiohttp

from lib.platforms.abc import PlatformABC, PlatformCTX
from lib.platforms.ctfd import CTFd
from lib.platforms.rctf import RCTF


class PlatformMeta(EnumMeta):
    def __iter__(cls):
        for platform in super().__iter__():
            if not platform.value:
                continue

            yield platform.value


class Platform(Enum, metaclass=PlatformMeta):
    CTFd = CTFd
    RCTF = RCTF
    UNKNOWN = None


async def match_platform(ctx: PlatformCTX) -> Optional[PlatformABC]:
    for platform in Platform:
        try:
            if await platform.match_platform(ctx):
                return platform
        except aiohttp.ClientError:
            continue

    return None
