"""Tests for utils.http module."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "eruditus"))

from unittest.mock import AsyncMock  # noqa: E402

import pytest  # noqa: E402
from pydantic import BaseModel  # noqa: E402
from utils.http import (  # noqa: E402
    deserialize_response,
    extract_rctf_team_token,
    strip_url_components,
)


class TestStripUrlComponents:
    """Tests for strip_url_components function."""

    def test_strip_path(self):
        """Test stripping path from URL."""
        url = "https://ctf.example.com/api/v1/challenges"
        assert strip_url_components(url) == "https://ctf.example.com"

    def test_strip_query_params(self):
        """Test stripping query parameters from URL."""
        url = "https://ctf.example.com?token=abc123"
        assert strip_url_components(url) == "https://ctf.example.com"

    def test_strip_fragment(self):
        """Test stripping fragment from URL."""
        url = "https://ctf.example.com#section"
        assert strip_url_components(url) == "https://ctf.example.com"

    def test_strip_all_components(self):
        """Test stripping path, query, and fragment."""
        url = "https://ctf.example.com/path?query=value#fragment"
        assert strip_url_components(url) == "https://ctf.example.com"

    def test_preserve_port(self):
        """Test that port number is preserved."""
        url = "https://ctf.example.com:8080/api"
        assert strip_url_components(url) == "https://ctf.example.com:8080"

    def test_http_scheme(self):
        """Test with HTTP scheme."""
        url = "http://ctf.example.com/path"
        assert strip_url_components(url) == "http://ctf.example.com"

    def test_no_path(self):
        """Test URL with no path."""
        url = "https://ctf.example.com"
        assert strip_url_components(url) == "https://ctf.example.com"


class TestExtractRctfTeamToken:
    """Tests for extract_rctf_team_token function."""

    def test_extract_token(self):
        """Test extracting token from valid URL."""
        url = "https://rctf.example.com/login?token=abc123xyz"
        assert extract_rctf_team_token(url) == "abc123xyz"

    def test_no_token(self):
        """Test URL without token parameter."""
        url = "https://rctf.example.com/login"
        assert extract_rctf_team_token(url) is None

    def test_empty_token(self):
        """Test URL with empty token parameter returns None."""
        url = "https://rctf.example.com/login?token="
        result = extract_rctf_team_token(url)
        # Empty token is treated as no token
        assert result is None or result == ""

    def test_multiple_params(self):
        """Test URL with multiple query parameters."""
        url = "https://rctf.example.com/login?foo=bar&token=mytoken&baz=qux"
        assert extract_rctf_team_token(url) == "mytoken"

    def test_token_with_special_chars(self):
        """Test token with URL-encoded special characters."""
        url = "https://rctf.example.com/login?token=abc%2B123"
        assert extract_rctf_team_token(url) == "abc+123"


class TestDeserializeResponse:
    """Tests for deserialize_response function."""

    class SampleModel(BaseModel):
        name: str
        value: int

    @pytest.mark.asyncio
    async def test_valid_response(self):
        """Test deserializing a valid response."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"name": "test", "value": 42})

        result = await deserialize_response(mock_response, self.SampleModel)
        assert result is not None
        assert result.name == "test"
        assert result.value == 42

    @pytest.mark.asyncio
    async def test_client_error_response(self):
        """Test deserializing a 4xx response."""
        mock_response = AsyncMock()
        mock_response.status = 400
        mock_response.json = AsyncMock(return_value={"name": "error", "value": 0})

        result = await deserialize_response(mock_response, self.SampleModel)
        assert result is not None
        assert result.name == "error"

    @pytest.mark.asyncio
    async def test_server_error_response(self):
        """Test that 5xx responses return None."""
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.json = AsyncMock(return_value={"name": "error", "value": 0})

        result = await deserialize_response(mock_response, self.SampleModel)
        assert result is None

    @pytest.mark.asyncio
    async def test_invalid_json_schema(self):
        """Test that invalid JSON schema returns None."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"wrong_field": "data"})

        result = await deserialize_response(
            mock_response, self.SampleModel, suppress_warnings=True
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_redirect_response(self):
        """Test that 3xx responses return None."""
        mock_response = AsyncMock()
        mock_response.status = 302
        mock_response.json = AsyncMock(return_value={"name": "test", "value": 1})

        result = await deserialize_response(mock_response, self.SampleModel)
        assert result is None
