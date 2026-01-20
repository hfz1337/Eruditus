"""Tests for miscellaneous utility modules."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "eruditus"))

from datetime import datetime, timezone  # noqa: E402

from utils.crypto import derive_colour  # noqa: E402
from utils.html import convert_attachment_url, extract_images_from_html  # noqa: E402
from utils.time import get_local_time  # noqa: E402


class TestGetLocalTime:
    """Tests for get_local_time function."""

    def test_returns_datetime(self):
        """Test that function returns a datetime object."""
        result = get_local_time()
        assert isinstance(result, datetime)

    def test_is_timezone_aware(self):
        """Test that returned datetime is timezone aware."""
        result = get_local_time()
        assert result.tzinfo is not None

    def test_reasonable_time(self):
        """Test that returned time is reasonable (within last minute)."""
        result = get_local_time()
        now_utc = datetime.now(timezone.utc)
        # Convert to UTC for comparison
        result_utc = result.astimezone(timezone.utc)
        diff = abs((now_utc - result_utc).total_seconds())
        assert diff < 60  # Within 1 minute


class TestDeriveColour:
    """Tests for derive_colour function."""

    def test_returns_integer(self):
        """Test that function returns an integer."""
        result = derive_colour("test_role")
        assert isinstance(result, int)

    def test_valid_rgb_range(self):
        """Test that result is within valid RGB range."""
        result = derive_colour("test_role")
        assert 0 <= result <= 0xFFFFFF

    def test_deterministic(self):
        """Test that same input gives same output."""
        result1 = derive_colour("my_role")
        result2 = derive_colour("my_role")
        assert result1 == result2

    def test_different_inputs_different_outputs(self):
        """Test that different inputs give different outputs."""
        result1 = derive_colour("role_a")
        result2 = derive_colour("role_b")
        assert result1 != result2

    def test_empty_string(self):
        """Test with empty string."""
        result = derive_colour("")
        assert isinstance(result, int)
        assert 0 <= result <= 0xFFFFFF

    def test_unicode_string(self):
        """Test with unicode characters."""
        result = derive_colour("CTF \u2605 Team")
        assert isinstance(result, int)
        assert 0 <= result <= 0xFFFFFF


class TestConvertAttachmentUrl:
    """Tests for convert_attachment_url function."""

    def test_absolute_url_unchanged(self):
        """Test that absolute URLs are not modified."""
        url = "https://files.example.com/file.zip"
        result = convert_attachment_url(url, "https://ctf.example.com")
        assert result == url

    def test_relative_url_converted(self):
        """Test that relative URLs are converted to absolute."""
        url = "/files/challenge.zip"
        base = "https://ctf.example.com"
        result = convert_attachment_url(url, base)
        assert result == "https://ctf.example.com/files/challenge.zip"

    def test_relative_url_no_leading_slash(self):
        """Test relative URL without leading slash."""
        url = "files/challenge.zip"
        base = "https://ctf.example.com/"
        result = convert_attachment_url(url, base)
        assert result == "https://ctf.example.com/files/challenge.zip"

    def test_base_url_with_trailing_slash(self):
        """Test base URL with trailing slash."""
        url = "/file.zip"
        base = "https://ctf.example.com/"
        result = convert_attachment_url(url, base)
        assert result == "https://ctf.example.com/file.zip"

    def test_no_base_url(self):
        """Test with no base URL provided."""
        url = "/file.zip"
        result = convert_attachment_url(url, None)
        assert result == "/file.zip"

    def test_http_url(self):
        """Test that HTTP URLs are not modified."""
        url = "http://files.example.com/file.zip"
        result = convert_attachment_url(url, "https://ctf.example.com")
        assert result == url


class TestExtractImagesFromHtml:
    """Tests for extract_images_from_html function."""

    def test_no_images(self):
        """Test HTML with no images."""
        html = "<p>No images here</p>"
        result = extract_images_from_html(html)
        assert result == []

    def test_single_image(self):
        """Test HTML with single image."""
        html = '<p>Check out <img src="/img/hint.png"></p>'
        result = extract_images_from_html(html, "https://ctf.example.com")
        assert len(result) == 1
        assert result[0].url == "https://ctf.example.com/img/hint.png"

    def test_multiple_images(self):
        """Test HTML with multiple images."""
        html = '<img src="/a.png"><img src="/b.png"><img src="/c.png">'
        result = extract_images_from_html(html, "https://ctf.example.com")
        assert len(result) == 3

    def test_absolute_image_url(self):
        """Test image with absolute URL."""
        html = '<img src="https://other.com/image.png">'
        result = extract_images_from_html(html, "https://ctf.example.com")
        assert len(result) == 1
        assert result[0].url == "https://other.com/image.png"

    def test_image_without_src(self):
        """Test image tag without src attribute."""
        html = '<img alt="No source">'
        result = extract_images_from_html(html)
        assert result == []

    def test_none_description(self):
        """Test with None description."""
        result = extract_images_from_html(None)
        assert result is None

    def test_empty_description(self):
        """Test with empty description."""
        result = extract_images_from_html("")
        assert result is None

    def test_no_base_url(self):
        """Test extraction without base URL."""
        html = '<img src="/image.png">'
        result = extract_images_from_html(html)
        assert len(result) == 1
        assert result[0].url == "/image.png"
