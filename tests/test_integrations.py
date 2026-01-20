"""Tests for integrations module."""

import pytest
from integrations.ctftime.models import (
    CTFTimeDiffType,
    CTFTimeParticipatedEvent,
    CTFTimeTeam,
    LeaderboardEntry,
)


class TestCTFTimeParticipatedEvent:
    """Tests for CTFTimeParticipatedEvent dataclass."""

    def test_create_event(self):
        """Test creating a participated event."""
        event = CTFTimeParticipatedEvent(
            place=5,
            event_id=1234,
            event_name="Example CTF 2024",
            ctf_points=150.5,
            rating_points=25.3,
        )
        assert event.place == 5
        assert event.event_id == 1234
        assert event.event_name == "Example CTF 2024"
        assert event.ctf_points == 150.5
        assert event.rating_points == 25.3

    def test_event_without_rating_points(self):
        """Test event with no rating points."""
        event = CTFTimeParticipatedEvent(
            place=1,
            event_id=5678,
            event_name="Small CTF",
            ctf_points=100.0,
            rating_points=None,
        )
        assert event.rating_points is None


class TestCTFTimeTeam:
    """Tests for CTFTimeTeam dataclass."""

    def test_create_team(self):
        """Test creating a team."""
        team = CTFTimeTeam(
            overall_points=500.0,
            overall_rating_place=42,
            country_place=5,
            country_code="US",
            participated_in={},
        )
        assert team.overall_points == 500.0
        assert team.overall_rating_place == 42
        assert team.country_place == 5
        assert team.country_code == "US"

    def test_team_diff_no_changes(self):
        """Test diff between identical teams."""
        team1 = CTFTimeTeam(
            overall_points=500.0,
            overall_rating_place=42,
            country_place=5,
            country_code="US",
            participated_in={},
        )
        team2 = CTFTimeTeam(
            overall_points=500.0,
            overall_rating_place=42,
            country_place=5,
            country_code="US",
            participated_in={},
        )
        diff = team1 - team2
        assert CTFTimeDiffType.OVERALL_POINTS_UPDATE not in diff
        assert CTFTimeDiffType.OVERALL_PLACE_UPDATE not in diff
        assert CTFTimeDiffType.COUNTRY_PLACE_UPDATE not in diff
        assert diff[CTFTimeDiffType.EVENT_UPDATE] == []

    def test_team_diff_points_changed(self):
        """Test diff when points changed."""
        team1 = CTFTimeTeam(
            overall_points=500.0,
            overall_rating_place=42,
            country_place=5,
            country_code="US",
            participated_in={},
        )
        team2 = CTFTimeTeam(
            overall_points=600.0,
            overall_rating_place=42,
            country_place=5,
            country_code="US",
            participated_in={},
        )
        diff = team1 - team2
        assert CTFTimeDiffType.OVERALL_POINTS_UPDATE in diff
        assert diff[CTFTimeDiffType.OVERALL_POINTS_UPDATE] == (500.0, 600.0)

    def test_team_diff_place_changed(self):
        """Test diff when overall place changed."""
        team1 = CTFTimeTeam(
            overall_points=500.0,
            overall_rating_place=42,
            country_place=5,
            country_code="US",
            participated_in={},
        )
        team2 = CTFTimeTeam(
            overall_points=500.0,
            overall_rating_place=35,
            country_place=5,
            country_code="US",
            participated_in={},
        )
        diff = team1 - team2
        assert CTFTimeDiffType.OVERALL_PLACE_UPDATE in diff
        assert diff[CTFTimeDiffType.OVERALL_PLACE_UPDATE] == (42, 35)

    def test_team_diff_country_place_changed(self):
        """Test diff when country place changed."""
        team1 = CTFTimeTeam(
            overall_points=500.0,
            overall_rating_place=42,
            country_place=5,
            country_code="US",
            participated_in={},
        )
        team2 = CTFTimeTeam(
            overall_points=500.0,
            overall_rating_place=42,
            country_place=3,
            country_code="US",
            participated_in={},
        )
        diff = team1 - team2
        assert CTFTimeDiffType.COUNTRY_PLACE_UPDATE in diff
        assert diff[CTFTimeDiffType.COUNTRY_PLACE_UPDATE] == (5, 3)

    def test_team_diff_event_updated(self):
        """Test diff when participated event updated."""
        event1 = CTFTimeParticipatedEvent(
            place=10,
            event_id=1234,
            event_name="CTF 2024",
            ctf_points=100.0,
            rating_points=10.0,
        )
        event2 = CTFTimeParticipatedEvent(
            place=5,
            event_id=1234,
            event_name="CTF 2024",
            ctf_points=150.0,
            rating_points=15.0,
        )
        team1 = CTFTimeTeam(
            overall_points=500.0,
            overall_rating_place=42,
            country_place=5,
            country_code="US",
            participated_in={1234: event1},
        )
        team2 = CTFTimeTeam(
            overall_points=500.0,
            overall_rating_place=42,
            country_place=5,
            country_code="US",
            participated_in={1234: event2},
        )
        diff = team1 - team2
        assert len(diff[CTFTimeDiffType.EVENT_UPDATE]) == 1
        old_event, new_event = diff[CTFTimeDiffType.EVENT_UPDATE][0]
        assert old_event.place == 10
        assert new_event.place == 5

    def test_team_diff_invalid_type(self):
        """Test diff with invalid type raises TypeError."""
        team = CTFTimeTeam(
            overall_points=500.0,
            overall_rating_place=42,
            country_place=5,
            country_code="US",
            participated_in={},
        )
        with pytest.raises(TypeError):
            _ = team - "not a team"

    def test_team_without_country(self):
        """Test team without country information."""
        team = CTFTimeTeam(
            overall_points=100.0,
            overall_rating_place=100,
            country_place=None,
            country_code=None,
            participated_in={},
        )
        assert team.country_place is None
        assert team.country_code is None


class TestLeaderboardEntry:
    """Tests for LeaderboardEntry dataclass."""

    def test_create_entry(self):
        """Test creating a leaderboard entry."""
        entry = LeaderboardEntry(
            position=1,
            country_position=1,
            team_id=12345,
            team_name="Top Team",
            country_code="US",
            points=1500.5,
            events=25,
        )
        assert entry.position == 1
        assert entry.team_id == 12345
        assert entry.team_name == "Top Team"
        assert entry.points == 1500.5
        assert entry.events == 25

    def test_entry_without_country(self):
        """Test entry without country information."""
        entry = LeaderboardEntry(
            position=50,
            country_position=None,
            team_id=99999,
            team_name="Anonymous Team",
            country_code=None,
            points=50.0,
            events=2,
        )
        assert entry.country_position is None
        assert entry.country_code is None


class TestCTFTimeDiffType:
    """Tests for CTFTimeDiffType enum."""

    def test_all_diff_types_exist(self):
        """Test that all expected diff types exist."""
        diff_types = [
            CTFTimeDiffType.OVERALL_POINTS_UPDATE,
            CTFTimeDiffType.OVERALL_PLACE_UPDATE,
            CTFTimeDiffType.COUNTRY_PLACE_UPDATE,
            CTFTimeDiffType.EVENT_UPDATE,
        ]
        assert len(diff_types) == 4

    def test_diff_types_are_unique(self):
        """Test that diff type values are unique."""
        values = [dt.value for dt in CTFTimeDiffType]
        assert len(values) == len(set(values))
