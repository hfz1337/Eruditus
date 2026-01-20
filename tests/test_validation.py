"""Tests for utils.validation module."""

import pytest
from utils.validation import in_range, is_empty_string


class TestInRange:
    """Tests for in_range function."""

    def test_value_in_range(self):
        """Test that values within range return True."""
        assert in_range(5, 1, 10) is True
        assert in_range(1, 1, 10) is True  # boundary
        assert in_range(10, 1, 10) is True  # boundary

    def test_value_out_of_range(self):
        """Test that values outside range return False."""
        assert in_range(0, 1, 10) is False
        assert in_range(11, 1, 10) is False
        assert in_range(-5, 1, 10) is False

    def test_negative_range(self):
        """Test with negative numbers."""
        assert in_range(-5, -10, 0) is True
        assert in_range(-15, -10, 0) is False

    def test_http_status_codes(self):
        """Test typical HTTP status code ranges."""
        # 2xx success
        assert in_range(200, 200, 299) is True
        assert in_range(201, 200, 299) is True
        assert in_range(299, 200, 299) is True

        # 4xx client errors
        assert in_range(400, 400, 499) is True
        assert in_range(404, 400, 499) is True

        # Out of range
        assert in_range(500, 200, 299) is False


class TestIsEmptyString:
    """Tests for is_empty_string function."""

    def test_none_is_empty(self):
        """Test that None is considered empty."""
        assert is_empty_string(None) is True

    def test_empty_string_is_empty(self):
        """Test that empty string is considered empty."""
        assert is_empty_string("") is True

    def test_whitespace_is_empty(self):
        """Test that whitespace-only strings are considered empty."""
        assert is_empty_string(" ") is True
        assert is_empty_string("   ") is True
        assert is_empty_string("\t") is True
        assert is_empty_string("\n") is True
        assert is_empty_string(" \t\n ") is True

    def test_non_empty_string(self):
        """Test that non-empty strings return False."""
        assert is_empty_string("hello") is False
        assert is_empty_string(" hello ") is False
        assert is_empty_string("0") is False

    def test_invalid_type_raises_error(self):
        """Test that non-string types raise TypeError."""
        with pytest.raises(TypeError):
            is_empty_string(123)

        with pytest.raises(TypeError):
            is_empty_string([])

        with pytest.raises(TypeError):
            is_empty_string({})
