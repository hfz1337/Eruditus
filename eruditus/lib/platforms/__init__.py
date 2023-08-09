from typing import List
from typing import Optional
from typing import Type

from .abc import PlatformABC
from .abc import PlatformCTX

from .ctfd import CTFd
from .rctf import RCTF


platforms: List[Type[PlatformABC]] = [
    CTFd,
    RCTF,
]


async def match_platform(ctx: PlatformCTX) -> Optional[Type[PlatformABC]]:
    for platform in platforms:
        if await platform.match_platform(ctx):
            return platform

    return None
