"""Tests for utils.formatting module."""

from utils.formatting import (
    extract_filename_from_url,
    html_to_markdown,
    sanitize_channel_name,
    truncate,
)


class TestTruncate:
    """Tests for truncate function."""

    def test_short_text_unchanged(self):
        """Test that short text is not truncated."""
        text = "Short text"
        assert truncate(text, max_len=100) == text

    def test_long_text_truncated(self):
        """Test that long text is truncated with ellipsis."""
        text = "A" * 100
        result = truncate(text, max_len=50)
        # etc = "\n[...]" (6 chars), so 44 + 6 = 50
        assert result == "A" * 44 + "\n[...]"
        assert len(result) == 50

    def test_boundary_not_truncated(self):
        """Test text just under the truncation threshold stays unchanged."""
        # Truncation happens when len(text) > max_len - len(etc)
        # etc = "\n[...]" = 6 chars, so threshold is 50 - 6 = 44
        text = "A" * 44
        result = truncate(text, max_len=50)
        assert result == text
        assert "[...]" not in result

    def test_boundary_truncated(self):
        """Test text just over the truncation threshold gets truncated."""
        text = "A" * 45  # One over the threshold
        result = truncate(text, max_len=50)
        assert result == "A" * 44 + "\n[...]"
        assert len(result) == 50

    def test_default_max_length(self):
        """Test default max length of 1024."""
        text = "A" * 2000
        result = truncate(text)
        # 1024 - 6 = 1018 chars + "\n[...]"
        assert result == "A" * 1018 + "\n[...]"
        assert len(result) == 1024


class TestSanitizeChannelName:
    """Tests for sanitize_channel_name function."""

    def test_lowercase_conversion(self):
        """Test that names are converted to lowercase."""
        assert sanitize_channel_name("CRYPTO") == "crypto"
        assert sanitize_channel_name("Web") == "web"

    def test_space_to_dash(self):
        """Test that spaces are converted to dashes."""
        assert sanitize_channel_name("web exploitation") == "web-exploitation"

    def test_special_chars_removed(self):
        """Test that special characters are removed."""
        assert sanitize_channel_name("crypto!@#$%") == "crypto"
        assert sanitize_channel_name("pwn&bin") == "pwnbin"

    def test_multiple_dashes_collapsed(self):
        """Test that multiple dashes are collapsed to single dash."""
        assert sanitize_channel_name("web  exploitation") == "web-exploitation"
        assert sanitize_channel_name("a--b") == "a-b"

    def test_allowed_characters(self):
        """Test that allowed characters are preserved."""
        assert sanitize_channel_name("crypto-101") == "crypto-101"
        assert sanitize_channel_name("web_pwn") == "web_pwn"

    def test_real_category_names(self):
        """Test with realistic CTF category names."""
        assert sanitize_channel_name("Web Exploitation") == "web-exploitation"
        assert sanitize_channel_name("Reverse Engineering") == "reverse-engineering"
        assert sanitize_channel_name("Pwn/Binary") == "pwnbinary"
        assert sanitize_channel_name("Crypto 101") == "crypto-101"


class TestHtmlToMarkdown:
    """Tests for html_to_markdown function."""

    def test_none_input(self):
        """Test that None input returns None."""
        assert html_to_markdown(None) is None

    def test_basic_html(self):
        """Test basic HTML conversion."""
        html = "<p>Hello <strong>world</strong></p>"
        result = html_to_markdown(html)
        assert "Hello" in result
        assert "world" in result

    def test_images_removed(self):
        """Test that images are removed."""
        html = '<p>Text</p><img src="test.png" alt="test"><p>More</p>'
        result = html_to_markdown(html)
        assert "![" not in result
        assert "test.png" not in result

    def test_multiline_collapsed(self):
        """Test that multiple newlines are collapsed."""
        html = "<p>Line 1</p>\n\n\n<p>Line 2</p>"
        result = html_to_markdown(html)
        assert "\n\n\n" not in result


class TestExtractFilenameFromUrl:
    """Tests for extract_filename_from_url function."""

    def test_simple_url(self):
        """Test extracting filename from simple URL."""
        url = "https://example.com/files/flag.txt"
        assert extract_filename_from_url(url) == "flag.txt"

    def test_url_with_query_params(self):
        """Test URL with query parameters."""
        url = "https://example.com/files/challenge.zip?token=abc123"
        assert extract_filename_from_url(url) == "challenge.zip"

    def test_url_with_fragment(self):
        """Test URL with fragment."""
        url = "https://example.com/files/readme.md#section"
        assert extract_filename_from_url(url) == "readme.md"

    def test_nested_path(self):
        """Test deeply nested path."""
        url = "https://example.com/a/b/c/d/file.bin"
        assert extract_filename_from_url(url) == "file.bin"

    def test_no_filename(self):
        """Test URL with no filename."""
        url = "https://example.com/"
        assert extract_filename_from_url(url) == ""
