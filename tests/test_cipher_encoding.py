"""Tests for cipher and encoding logic (without Discord dependencies)."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "eruditus"))

from base64 import b32decode, b32encode, b64decode, b64encode  # noqa: E402
from binascii import hexlify, unhexlify  # noqa: E402
from urllib.parse import quote, unquote  # noqa: E402

from commands.cipher import ClassicCiphers  # noqa: E402


class TestCaesarCipher:
    """Tests for Caesar cipher implementation."""

    def test_shift_by_one(self):
        """Test shifting by 1."""
        assert ClassicCiphers.caesar("abc", 1) == "bcd"

    def test_shift_by_three(self):
        """Test classic Caesar shift by 3."""
        assert ClassicCiphers.caesar("abc", 3) == "def"

    def test_shift_wraps_around(self):
        """Test that shift wraps around alphabet."""
        assert ClassicCiphers.caesar("xyz", 3) == "abc"

    def test_preserves_case(self):
        """Test that case is preserved."""
        assert ClassicCiphers.caesar("AbC", 1) == "BcD"

    def test_preserves_non_alpha(self):
        """Test that non-alphabetic characters are preserved."""
        assert ClassicCiphers.caesar("a1b2c3!", 1) == "b1c2d3!"

    def test_decrypt_with_negative_key(self):
        """Test decryption using negative key."""
        encrypted = ClassicCiphers.caesar("hello", 5)
        decrypted = ClassicCiphers.caesar(encrypted, -5)
        assert decrypted == "hello"

    def test_full_rotation(self):
        """Test that shift by 26 returns original."""
        assert ClassicCiphers.caesar("hello", 26) == "hello"

    def test_empty_string(self):
        """Test with empty string."""
        assert ClassicCiphers.caesar("", 5) == ""

    def test_uppercase_wraps(self):
        """Test uppercase letters wrap around."""
        assert ClassicCiphers.caesar("XYZ", 3) == "ABC"


class TestRot13:
    """Tests for ROT13 cipher."""

    def test_rot13_basic(self):
        """Test basic ROT13."""
        assert ClassicCiphers.rot13("hello") == "uryyb"

    def test_rot13_is_self_inverse(self):
        """Test that applying ROT13 twice returns original."""
        original = "Hello World!"
        assert ClassicCiphers.rot13(ClassicCiphers.rot13(original)) == original

    def test_rot13_preserves_case(self):
        """Test that ROT13 preserves case."""
        assert ClassicCiphers.rot13("ABC") == "NOP"
        assert ClassicCiphers.rot13("abc") == "nop"

    def test_rot13_preserves_non_alpha(self):
        """Test that ROT13 preserves non-alphabetic characters."""
        assert ClassicCiphers.rot13("a1b2c3") == "n1o2p3"


class TestAtbashCipher:
    """Tests for Atbash cipher."""

    def test_atbash_basic(self):
        """Test basic Atbash cipher."""
        assert ClassicCiphers.atbash("abc") == "zyx"

    def test_atbash_is_self_inverse(self):
        """Test that applying Atbash twice returns original."""
        original = "Hello World!"
        assert ClassicCiphers.atbash(ClassicCiphers.atbash(original)) == original

    def test_atbash_preserves_case(self):
        """Test that Atbash preserves case."""
        assert ClassicCiphers.atbash("ABC") == "ZYX"
        assert ClassicCiphers.atbash("abc") == "zyx"
        assert ClassicCiphers.atbash("AbC") == "ZyX"

    def test_atbash_preserves_non_alpha(self):
        """Test that Atbash preserves non-alphabetic characters."""
        assert ClassicCiphers.atbash("a1b2!") == "z1y2!"

    def test_atbash_full_alphabet(self):
        """Test Atbash on full alphabet."""
        assert (
            ClassicCiphers.atbash("abcdefghijklmnopqrstuvwxyz")
            == "zyxwvutsrqponmlkjihgfedcba"
        )


class TestBase64Encoding:
    """Tests for Base64 encoding logic."""

    def test_encode(self):
        """Test Base64 encoding."""
        data = "Hello, World!"
        result = b64encode(data.encode()).decode()
        assert result == "SGVsbG8sIFdvcmxkIQ=="

    def test_decode(self):
        """Test Base64 decoding."""
        data = "SGVsbG8sIFdvcmxkIQ=="
        result = b64decode(data).decode()
        assert result == "Hello, World!"

    def test_roundtrip(self):
        """Test encoding then decoding returns original."""
        original = "Test data 123!"
        encoded = b64encode(original.encode()).decode()
        decoded = b64decode(encoded).decode()
        assert decoded == original


class TestBase32Encoding:
    """Tests for Base32 encoding logic."""

    def test_encode(self):
        """Test Base32 encoding."""
        data = "Hello"
        result = b32encode(data.encode()).decode()
        assert result == "JBSWY3DP"

    def test_decode(self):
        """Test Base32 decoding."""
        data = "JBSWY3DP"
        result = b32decode(data).decode()
        assert result == "Hello"

    def test_roundtrip(self):
        """Test encoding then decoding returns original."""
        original = "CTF{flag}"
        encoded = b32encode(original.encode()).decode()
        decoded = b32decode(encoded).decode()
        assert decoded == original


class TestHexEncoding:
    """Tests for hex encoding logic."""

    def test_encode(self):
        """Test hex encoding."""
        data = "abc"
        result = hexlify(data.encode()).decode()
        assert result == "616263"

    def test_decode(self):
        """Test hex decoding."""
        data = "616263"
        result = unhexlify(data).decode()
        assert result == "abc"

    def test_roundtrip(self):
        """Test encoding then decoding returns original."""
        original = "flag{test}"
        encoded = hexlify(original.encode()).decode()
        decoded = unhexlify(encoded).decode()
        assert decoded == original


class TestBinaryEncoding:
    """Tests for binary encoding logic."""

    def test_encode(self):
        """Test binary encoding."""
        data = "A"
        result = bin(int.from_bytes(data.encode(), "big"))[2:]
        result = "0" * (8 - len(result) % 8) + result if len(result) % 8 else result
        assert result == "01000001"

    def test_decode(self):
        """Test binary decoding."""
        data = "01000001"
        value = int(data, 2)
        result = value.to_bytes(value.bit_length() // 8 + 1, "big").decode()
        # Strip leading null bytes
        result = result.lstrip("\x00")
        assert result == "A"

    def test_multi_char_encode(self):
        """Test encoding multiple characters."""
        data = "Hi"
        result = bin(int.from_bytes(data.encode(), "big"))[2:]
        result = "0" * (8 - len(result) % 8) + result if len(result) % 8 else result
        assert result == "0100100001101001"


class TestURLEncoding:
    """Tests for URL encoding logic."""

    def test_encode_spaces(self):
        """Test URL encoding spaces."""
        data = "hello world"
        result = quote(data)
        assert result == "hello%20world"

    def test_encode_special_chars(self):
        """Test URL encoding special characters."""
        data = "a=b&c=d"
        result = quote(data)
        assert "%3D" in result  # = character
        assert "%26" in result  # & character

    def test_decode(self):
        """Test URL decoding."""
        data = "hello%20world"
        result = unquote(data)
        assert result == "hello world"

    def test_roundtrip(self):
        """Test encoding then decoding returns original."""
        original = "test?param=value&other=123"
        encoded = quote(original)
        decoded = unquote(encoded)
        assert decoded == original

    def test_safe_characters_not_encoded(self):
        """Test that safe characters are not encoded by default."""
        data = "abc123"
        result = quote(data)
        assert result == "abc123"
