"""Tests for constants module."""

from constants import (
    CategoryPrefixes,
    ChannelNames,
    EmbedColours,
    Emojis,
    ErrorMessages,
    ThreadPrefixes,
)


class TestEmojis:
    """Tests for Emojis constants."""

    def test_status_emojis_defined(self):
        """Test that status emojis are defined."""
        assert Emojis.SUCCESS == "✅"
        assert Emojis.ERROR == "❌"
        assert Emojis.WARNING == "⚠️"

    def test_challenge_status_emojis(self):
        """Test challenge status emojis."""
        assert Emojis.FIRST_BLOOD == "🩸"
        assert Emojis.SOLVED == "✅"
        assert Emojis.UNSOLVED == "❌"

    def test_ctf_status_emojis(self):
        """Test CTF status emojis."""
        assert Emojis.LIVE == "🔴"
        assert Emojis.PENDING == "⏰"
        assert Emojis.ENDED == "🏁"


class TestChannelNames:
    """Tests for ChannelNames constants."""

    def test_standard_channels(self):
        """Test that standard channel names are defined."""
        assert ChannelNames.GENERAL == "general"
        assert ChannelNames.ANNOUNCEMENTS == "announcements"
        assert ChannelNames.CREDENTIALS == "credentials"
        assert ChannelNames.SCOREBOARD == "scoreboard"
        assert ChannelNames.SOLVES == "solves"
        assert ChannelNames.NOTES == "notes"
        assert ChannelNames.BOT_CMDS == "bot-cmds"


class TestThreadPrefixes:
    """Tests for ThreadPrefixes constants."""

    def test_prefix_format(self):
        """Test that prefixes end with dash."""
        assert ThreadPrefixes.SOLVED.endswith("-")
        assert ThreadPrefixes.UNSOLVED.endswith("-")
        assert ThreadPrefixes.FIRST_BLOOD.endswith("-")

    def test_get_prefix_first_blood(self):
        """Test get_prefix returns first blood prefix."""
        prefix = ThreadPrefixes.get_prefix(solved=True, blooded=True)
        assert prefix == ThreadPrefixes.FIRST_BLOOD

    def test_get_prefix_solved(self):
        """Test get_prefix returns solved prefix."""
        prefix = ThreadPrefixes.get_prefix(solved=True, blooded=False)
        assert prefix == ThreadPrefixes.SOLVED

    def test_get_prefix_unsolved(self):
        """Test get_prefix returns unsolved prefix."""
        prefix = ThreadPrefixes.get_prefix(solved=False, blooded=False)
        assert prefix == ThreadPrefixes.UNSOLVED

    def test_blooded_takes_precedence(self):
        """Test that blooded=True takes precedence even if solved=False."""
        # This is an edge case - blooded should imply solved
        prefix = ThreadPrefixes.get_prefix(solved=False, blooded=True)
        assert prefix == ThreadPrefixes.FIRST_BLOOD


class TestCategoryPrefixes:
    """Tests for CategoryPrefixes constants."""

    def test_all_prefixes_tuple(self):
        """Test that ALL contains the emoji components."""
        assert Emojis.SLEEPING in CategoryPrefixes.ALL
        assert Emojis.ACTIVE in CategoryPrefixes.ALL
        assert Emojis.MAXED in CategoryPrefixes.ALL

    def test_prefix_contains_emoji(self):
        """Test that prefixes contain the correct emojis."""
        assert Emojis.SLEEPING in CategoryPrefixes.SLEEPING
        assert Emojis.ACTIVE in CategoryPrefixes.ACTIVE
        assert Emojis.MAXED in CategoryPrefixes.MAXED


class TestEmbedColours:
    """Tests for EmbedColours constants."""

    def test_colours_are_discord_colours(self):
        """Test that colours are Discord Colour objects."""
        import discord

        assert isinstance(EmbedColours.INFO, discord.Colour)
        assert isinstance(EmbedColours.SUCCESS, discord.Colour)
        assert isinstance(EmbedColours.ERROR, discord.Colour)


class TestErrorMessages:
    """Tests for ErrorMessages constants."""

    def test_context_errors(self):
        """Test context error messages exist."""
        assert "CTF channel" in ErrorMessages.NOT_IN_CTF_CHANNEL
        assert "challenge thread" in ErrorMessages.NOT_IN_CHALLENGE_THREAD

    def test_ctf_errors(self):
        """Test CTF error messages exist."""
        assert ErrorMessages.CTF_NOT_FOUND
        assert ErrorMessages.CTF_ALREADY_EXISTS
        assert ErrorMessages.CTF_ARCHIVED

    def test_challenge_errors(self):
        """Test challenge error messages exist."""
        assert ErrorMessages.CHALLENGE_NOT_FOUND
        assert ErrorMessages.CHALLENGE_ALREADY_EXISTS
        assert ErrorMessages.CHALLENGE_ALREADY_SOLVED

    def test_platform_errors(self):
        """Test platform error messages exist."""
        assert ErrorMessages.PLATFORM_NOT_SUPPORTED
        assert ErrorMessages.NO_CREDENTIALS
