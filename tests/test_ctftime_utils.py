"""Tests for CTFtime utilities."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "eruditus"))

from datetime import timezone  # noqa: E402

from integrations.ctftime.utils import ctftime_date_to_datetime  # noqa: E402


class TestCtftimeDateToDatetime:
    """Tests for ctftime_date_to_datetime function."""

    def test_standard_format(self):
        """Test standard CTFtime date format."""
        date_str = "Fri, 15 March 2024, 12:00 UTC"
        result = ctftime_date_to_datetime(date_str)

        assert result.year == 2024
        assert result.month == 3
        assert result.day == 15
        assert result.hour == 12
        assert result.minute == 0
        assert result.tzinfo == timezone.utc

    def test_abbreviated_month_with_dot(self):
        """Test date with abbreviated month (with dot)."""
        date_str = "Mon, 01 Jan. 2024, 00:00 UTC"
        result = ctftime_date_to_datetime(date_str)

        assert result.year == 2024
        assert result.month == 1
        assert result.day == 1

    def test_september_correction(self):
        """Test that 'Sept' is corrected to 'Sep'."""
        date_str = "Sun, 15 Sept. 2024, 18:30 UTC"
        result = ctftime_date_to_datetime(date_str)

        assert result.month == 9
        assert result.day == 15

    def test_full_month_name(self):
        """Test with full month name."""
        date_str = "Wed, 25 December 2024, 08:00 UTC"
        result = ctftime_date_to_datetime(date_str)

        assert result.month == 12
        assert result.day == 25

    def test_timezone_aware(self):
        """Test that result is timezone aware."""
        date_str = "Fri, 01 February 2024, 14:30 UTC"
        result = ctftime_date_to_datetime(date_str)

        assert result.tzinfo is not None
        assert result.tzinfo == timezone.utc

    def test_different_weekdays(self):
        """Test various weekdays parse correctly."""
        weekdays = [
            ("Mon, 01 January 2024, 00:00 UTC", 0),  # Monday
            ("Tue, 02 January 2024, 00:00 UTC", 1),  # Tuesday
            ("Wed, 03 January 2024, 00:00 UTC", 2),  # Wednesday
            ("Thu, 04 January 2024, 00:00 UTC", 3),  # Thursday
            ("Fri, 05 January 2024, 00:00 UTC", 4),  # Friday
            ("Sat, 06 January 2024, 00:00 UTC", 5),  # Saturday
            ("Sun, 07 January 2024, 00:00 UTC", 6),  # Sunday
        ]
        for date_str, expected_weekday in weekdays:
            result = ctftime_date_to_datetime(date_str)
            assert result.weekday() == expected_weekday

    def test_end_of_day(self):
        """Test time at end of day."""
        date_str = "Fri, 31 December 2024, 23:59 UTC"
        result = ctftime_date_to_datetime(date_str)

        assert result.hour == 23
        assert result.minute == 59

    def test_abbreviated_months(self):
        """Test all abbreviated months with dot."""
        months = [
            ("Jan.", 1),
            ("Feb.", 2),
            ("Mar.", 3),
            ("Apr.", 4),
            ("May.", 5),
            ("Jun.", 6),
            ("Jul.", 7),
            ("Aug.", 8),
            ("Sep.", 9),
            ("Oct.", 10),
            ("Nov.", 11),
            ("Dec.", 12),
        ]
        for month_abbr, expected_month in months:
            date_str = f"Mon, 15 {month_abbr} 2024, 12:00 UTC"
            result = ctftime_date_to_datetime(date_str)
            assert result.month == expected_month, f"Failed for {month_abbr}"
