"""CTF platform integrations."""

from enum import Enum
from typing import Optional

import aiohttp
from platforms.base import PlatformABC, PlatformCTX


class Platform(Enum):
    """Supported CTF platforms."""

    CTFd = "ctfd"
    RCTF = "rctf"

    @property
    def impl(self) -> type[PlatformABC]:
        """Get the platform implementation class."""
        from platforms.ctfd import CTFd
        from platforms.rctf import RCTF

        return {
            Platform.CTFd: CTFd,
            Platform.RCTF: RCTF,
        }[self]


async def match_platform(ctx: PlatformCTX) -> Optional["Platform"]:
    """Match a URL to a supported platform.

    Args:
        ctx: The platform context with credentials.

    Returns:
        The matched Platform enum or None if not supported.
    """
    for platform in Platform:
        try:
            if await platform.impl.match_platform(ctx):
                return platform
        except aiohttp.ClientError:
            continue

    return None


__all__ = [
    "Platform",
    "PlatformABC",
    "PlatformCTX",
    "match_platform",
]
