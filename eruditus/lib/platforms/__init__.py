from enum import Enum, EnumMeta
from typing import Optional

from lib.platforms.abc import PlatformABC, PlatformCTX
from lib.platforms.ctfd import CTFd
from lib.platforms.rctf import RCTF


class PlatformMeta(EnumMeta):
    def __iter__(cls):
        for platform in super().__iter__():
            if platform.value:
                yield platform.value


class Platform(Enum, metaclass=PlatformMeta):
    CTFd = CTFd
    RCTF = RCTF
    UNKNOWN = None


async def match_platform(ctx: PlatformCTX) -> Optional[PlatformABC]:
    for platform in Platform:
        if await platform.match_platform(ctx):
            return platform

    return None
