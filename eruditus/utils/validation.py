"""Validation utilities."""

from typing import Optional


def in_range(value: int, minimal: int, maximum: int) -> bool:
    """Check whether number is in desired range.

    Args:
        value: The value that is going to be checked.
        minimal: Min value.
        maximum: Max value.

    Returns:
        True or false.
    """
    return minimal <= value <= maximum


def is_empty_string(value: Optional[str]) -> bool:
    """Check whether a string is empty.

    Args:
        value: The string that is going to be checked.

    Returns:
        True if the string is empty or None, False otherwise.

    Raises:
        TypeError: if `value` is of type other than `None` or `str`.
    """
    if value is not None and not isinstance(value, str):
        raise TypeError("Value must be either None or a string")
    return value is None or value.strip() == ""
