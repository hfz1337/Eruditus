"""Cryptographic utilities."""

from hashlib import md5


def derive_colour(role_name: str) -> int:
    """Derive a color for a role by taking its MD5 hash and using the first three
    bytes as the color.

    Args:
        role_name: Name of the role we wish to set a color for.

    Returns:
        An integer representing an RGB color.
    """
    return int(md5(role_name.encode()).hexdigest()[:6], 16)
