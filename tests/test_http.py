"""Tests for utils.http module."""

from utils.http import extract_rctf_team_token, strip_url_components


class TestStripUrlComponents:
    """Tests for strip_url_components function."""

    def test_strips_path(self):
        """Test that path is stripped."""
        url = "https://ctf.example.com/challenges"
        assert strip_url_components(url) == "https://ctf.example.com"

    def test_strips_query_params(self):
        """Test that query parameters are stripped."""
        url = "https://ctf.example.com?id=123&page=1"
        assert strip_url_components(url) == "https://ctf.example.com"

    def test_strips_fragment(self):
        """Test that fragment is stripped."""
        url = "https://ctf.example.com#section"
        assert strip_url_components(url) == "https://ctf.example.com"

    def test_strips_all_components(self):
        """Test stripping path, query, and fragment together."""
        url = "https://ctf.example.com/api/v1/challenges?limit=10#top"
        assert strip_url_components(url) == "https://ctf.example.com"

    def test_preserves_port(self):
        """Test that port number is preserved."""
        url = "https://ctf.example.com:8443/challenges"
        assert strip_url_components(url) == "https://ctf.example.com:8443"

    def test_http_scheme(self):
        """Test with HTTP scheme."""
        url = "http://ctf.example.com/login"
        assert strip_url_components(url) == "http://ctf.example.com"

    def test_base_url_unchanged(self):
        """Test that base URL without path is unchanged."""
        url = "https://ctf.example.com"
        assert strip_url_components(url) == "https://ctf.example.com"


class TestExtractRctfTeamToken:
    """Tests for extract_rctf_team_token function."""

    def test_extracts_token(self):
        """Test extracting token from valid invite URL."""
        url = "https://rctf.example.com/login?token=abc123xyz"
        assert extract_rctf_team_token(url) == "abc123xyz"

    def test_token_with_special_chars(self):
        """Test token with URL-safe special characters."""
        url = "https://rctf.example.com/login?token=abc-123_xyz"
        assert extract_rctf_team_token(url) == "abc-123_xyz"

    def test_multiple_params(self):
        """Test URL with multiple query parameters."""
        url = "https://rctf.example.com/login?ref=invite&token=mytoken&utm=test"
        assert extract_rctf_team_token(url) == "mytoken"

    def test_no_token_returns_none(self):
        """Test URL without token parameter returns None."""
        url = "https://rctf.example.com/login?ref=invite"
        assert extract_rctf_team_token(url) is None

    def test_empty_url(self):
        """Test with URL that has no query string."""
        url = "https://rctf.example.com/login"
        assert extract_rctf_team_token(url) is None

    def test_different_path(self):
        """Test with different path structure."""
        url = "https://rctf.example.com/team/join?token=teamtoken123"
        assert extract_rctf_team_token(url) == "teamtoken123"
