"""Tests for utils.visualization module."""

import io

from platforms.base import CategoryStats, TeamCategoryStats
from utils.visualization import plot_category_radar


def _make_team_stats(
    team_name: str, is_me: bool, stats: list[CategoryStats]
) -> TeamCategoryStats:
    """Helper to create TeamCategoryStats."""
    return TeamCategoryStats(team_name=team_name, is_me=is_me, stats=stats)


class TestPlotCategoryRadar:
    """Tests for plot_category_radar function."""

    def test_returns_bytesio_buffer(self):
        """Test that the function returns a BytesIO buffer."""
        stats = [
            CategoryStats(category="Web", total=5, solved=3),
            CategoryStats(category="Crypto", total=4, solved=2),
            CategoryStats(category="Pwn", total=3, solved=1),
        ]
        teams_stats = [_make_team_stats("Our Team", True, stats)]
        result = plot_category_radar(teams_stats)
        assert isinstance(result, io.BytesIO)

    def test_empty_stats_returns_none(self):
        """Test that empty teams_stats list returns None."""
        result = plot_category_radar([])
        assert result is None

    def test_empty_category_stats_returns_none(self):
        """Test that empty category stats returns None."""
        teams_stats = [_make_team_stats("Our Team", True, [])]
        result = plot_category_radar(teams_stats)
        assert result is None

    def test_single_category_pads_to_three(self):
        """Test that a single category is padded to 3 for proper radar shape."""
        stats = [CategoryStats(category="Web", total=5, solved=3)]
        teams_stats = [_make_team_stats("Our Team", True, stats)]
        result = plot_category_radar(teams_stats)
        assert isinstance(result, io.BytesIO)

    def test_two_categories_pads_to_three(self):
        """Test that two categories are padded to 3 for proper radar shape."""
        stats = [
            CategoryStats(category="Web", total=5, solved=3),
            CategoryStats(category="Crypto", total=4, solved=2),
        ]
        teams_stats = [_make_team_stats("Our Team", True, stats)]
        result = plot_category_radar(teams_stats)
        assert isinstance(result, io.BytesIO)

    def test_many_categories(self):
        """Test that many categories work correctly."""
        stats = [
            CategoryStats(category="Web", total=5, solved=3),
            CategoryStats(category="Crypto", total=4, solved=2),
            CategoryStats(category="Pwn", total=3, solved=1),
            CategoryStats(category="Rev", total=6, solved=4),
            CategoryStats(category="Forensics", total=2, solved=0),
            CategoryStats(category="Misc", total=5, solved=5),
        ]
        teams_stats = [_make_team_stats("Our Team", True, stats)]
        result = plot_category_radar(teams_stats)
        assert isinstance(result, io.BytesIO)

    def test_all_solved(self):
        """Test chart with all challenges solved."""
        stats = [
            CategoryStats(category="Web", total=5, solved=5),
            CategoryStats(category="Crypto", total=4, solved=4),
            CategoryStats(category="Pwn", total=3, solved=3),
        ]
        teams_stats = [_make_team_stats("Our Team", True, stats)]
        result = plot_category_radar(teams_stats)
        assert isinstance(result, io.BytesIO)

    def test_none_solved(self):
        """Test chart with no challenges solved."""
        stats = [
            CategoryStats(category="Web", total=5, solved=0),
            CategoryStats(category="Crypto", total=4, solved=0),
            CategoryStats(category="Pwn", total=3, solved=0),
        ]
        teams_stats = [_make_team_stats("Our Team", True, stats)]
        result = plot_category_radar(teams_stats)
        assert isinstance(result, io.BytesIO)

    def test_buffer_contains_png_data(self):
        """Test that the buffer contains valid PNG data."""
        stats = [
            CategoryStats(category="Web", total=5, solved=3),
            CategoryStats(category="Crypto", total=4, solved=2),
            CategoryStats(category="Pwn", total=3, solved=1),
        ]
        teams_stats = [_make_team_stats("Our Team", True, stats)]
        result = plot_category_radar(teams_stats)
        assert result is not None
        # Check PNG magic bytes
        png_header = result.read(8)
        assert png_header == b"\x89PNG\r\n\x1a\n"

    def test_buffer_position_reset(self):
        """Test that the buffer position is reset to the beginning."""
        stats = [
            CategoryStats(category="Web", total=5, solved=3),
            CategoryStats(category="Crypto", total=4, solved=2),
            CategoryStats(category="Pwn", total=3, solved=1),
        ]
        teams_stats = [_make_team_stats("Our Team", True, stats)]
        result = plot_category_radar(teams_stats)
        assert result is not None
        assert result.tell() == 0

    def test_zero_total_challenges(self):
        """Test handling of categories with zero total challenges."""
        stats = [
            CategoryStats(category="Web", total=0, solved=0),
            CategoryStats(category="Crypto", total=0, solved=0),
            CategoryStats(category="Pwn", total=0, solved=0),
        ]
        teams_stats = [_make_team_stats("Our Team", True, stats)]
        result = plot_category_radar(teams_stats)
        assert isinstance(result, io.BytesIO)

    def test_special_characters_in_category_name(self):
        """Test handling of special characters in category names."""
        stats = [
            CategoryStats(category="Web/API", total=5, solved=3),
            CategoryStats(category="Crypto (Hard)", total=4, solved=2),
            CategoryStats(category="Pwn & Rev", total=3, solved=1),
        ]
        teams_stats = [_make_team_stats("Our Team", True, stats)]
        result = plot_category_radar(teams_stats)
        assert isinstance(result, io.BytesIO)

    def test_multiple_teams(self):
        """Test chart with multiple teams."""
        our_stats = [
            CategoryStats(category="Web", total=5, solved=3),
            CategoryStats(category="Crypto", total=4, solved=2),
            CategoryStats(category="Pwn", total=3, solved=1),
        ]
        their_stats = [
            CategoryStats(category="Web", total=5, solved=4),
            CategoryStats(category="Crypto", total=4, solved=3),
            CategoryStats(category="Pwn", total=3, solved=2),
        ]
        teams_stats = [
            _make_team_stats("Our Team", True, our_stats),
            _make_team_stats("Top Team", False, their_stats),
        ]
        result = plot_category_radar(teams_stats)
        assert isinstance(result, io.BytesIO)

    def test_comparison_team_better_performance(self):
        """Test chart where comparison team solved more challenges."""
        our_stats = [
            CategoryStats(category="Web", total=5, solved=1),
            CategoryStats(category="Crypto", total=4, solved=0),
            CategoryStats(category="Pwn", total=3, solved=0),
        ]
        their_stats = [
            CategoryStats(category="Web", total=5, solved=5),
            CategoryStats(category="Crypto", total=4, solved=4),
            CategoryStats(category="Pwn", total=3, solved=3),
        ]
        teams_stats = [
            _make_team_stats("Our Team", True, our_stats),
            _make_team_stats("Top Team", False, their_stats),
        ]
        result = plot_category_radar(teams_stats)
        assert isinstance(result, io.BytesIO)
