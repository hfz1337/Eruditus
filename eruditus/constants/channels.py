"""Channel-related constants."""

from constants.emojis import Emojis


class ChannelNames:
    """Standard channel names for CTF categories."""

    GENERAL = "general"
    ANNOUNCEMENTS = "announcements"
    CREDENTIALS = "credentials"
    SCOREBOARD = "scoreboard"
    SOLVES = "solves"
    NOTES = "notes"
    BOT_CMDS = "bot-cmds"


class ThreadPrefixes:
    """Thread name prefixes for challenge status."""

    SOLVED = f"{Emojis.SOLVED}-"
    UNSOLVED = f"{Emojis.UNSOLVED}-"
    FIRST_BLOOD = f"{Emojis.FIRST_BLOOD}-"

    @staticmethod
    def get_prefix(solved: bool, blooded: bool) -> str:
        """Get the appropriate thread prefix based on solve status.

        Args:
            solved: Whether the challenge is solved.
            blooded: Whether this was a first blood.

        Returns:
            The appropriate emoji prefix.
        """
        if blooded:
            return ThreadPrefixes.FIRST_BLOOD
        elif solved:
            return ThreadPrefixes.SOLVED
        return ThreadPrefixes.UNSOLVED


class CategoryPrefixes:
    """Category channel name prefixes for status indication."""

    SLEEPING = f"{Emojis.SLEEPING}-"  # 💤- No active challenges
    ACTIVE = f"{Emojis.ACTIVE}-"  # 🔄- Has unsolved challenges
    MAXED = f"{Emojis.MAXED}-"  # 🎯- All challenges solved

    ALL = (Emojis.SLEEPING, Emojis.ACTIVE, Emojis.MAXED)
