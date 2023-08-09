from typing import List
from typing import Optional
from typing import Type

from .abc import PlatformABC
from .abc import PlatformCTX
from .ctfd import CTFd

platforms: List[Type[PlatformABC]] = [
    CTFd
]


async def match_platform(ctx: PlatformCTX) -> Optional[Type[PlatformABC]]:
    for platform in platforms:
        if await platform.match_platform(ctx):
            return platform

    return None
