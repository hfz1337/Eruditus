"""Pytest configuration and fixtures."""

import sys
from pathlib import Path

import pytest

# Add eruditus to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "eruditus"))


@pytest.fixture
def sample_html():
    """Sample HTML content for testing."""
    return """
    <h1>Challenge Description</h1>
    <p>This is a <strong>test</strong> challenge.</p>
    <img src="https://example.com/image.png" alt="test">
    <p>Find the flag!</p>
    """


@pytest.fixture
def sample_urls():
    """Sample URLs for testing."""
    return {
        "full": "https://ctf.example.com/challenges?id=123#section",
        "base": "https://ctf.example.com",
        "with_path": "https://ctf.example.com/api/v1/challenges",
        "rctf_invite": "https://rctf.example.com/login?token=abc123xyz",
        "file_url": "https://files.example.com/attachments/flag.txt",
    }
