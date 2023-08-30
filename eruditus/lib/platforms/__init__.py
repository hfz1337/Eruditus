from enum import Enum, EnumMeta
from typing import Optional

from .abc import PlatformCTX
from .ctfd import CTFd
from .rctf import RCTF


class PlatformMeta(EnumMeta):
    def __iter__(cls):
        for platform in super().__iter__():
            yield platform.value


class Platform(Enum, metaclass=PlatformMeta):
    CTFd = CTFd
    RCTF = RCTF


async def match_platform(ctx: PlatformCTX) -> Optional[Platform]:
    for platform in Platform:
        if await platform.match_platform(ctx):
            return platform

    return None
