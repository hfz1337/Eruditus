"""Tests for models module."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "eruditus"))

from models.enums import (  # noqa: E402
    CPUArchitecture,
    CTFStatusMode,
    EncodingOperationMode,
    OSType,
    Permissions,
    Privacy,
)


class TestCPUArchitecture:
    """Tests for CPUArchitecture enum."""

    def test_all_architectures_exist(self):
        """Test that all expected architectures exist."""
        archs = [
            CPUArchitecture.x86,
            CPUArchitecture.x64,
            CPUArchitecture.arm,
            CPUArchitecture.armthumb,
            CPUArchitecture.riscv,
        ]
        assert len(archs) == 5

    def test_values_are_unique(self):
        """Test that architecture values are unique."""
        values = [arch.value for arch in CPUArchitecture]
        assert len(values) == len(set(values))

    def test_x86_value(self):
        """Test x86 has expected value."""
        assert CPUArchitecture.x86.value == 1

    def test_x64_value(self):
        """Test x64 has expected value."""
        assert CPUArchitecture.x64.value == 2


class TestEncodingOperationMode:
    """Tests for EncodingOperationMode enum."""

    def test_encode_mode(self):
        """Test encode mode exists and has correct value."""
        assert EncodingOperationMode.encode.value == 1

    def test_decode_mode(self):
        """Test decode mode exists and has correct value."""
        assert EncodingOperationMode.decode.value == 2

    def test_only_two_modes(self):
        """Test that only encode and decode exist."""
        assert len(EncodingOperationMode) == 2


class TestCTFStatusMode:
    """Tests for CTFStatusMode enum."""

    def test_active_mode(self):
        """Test active mode."""
        assert CTFStatusMode.active.value == 1

    def test_all_mode(self):
        """Test all mode."""
        assert CTFStatusMode.all.value == 2

    def test_mode_count(self):
        """Test total number of modes."""
        assert len(CTFStatusMode) == 2


class TestPermissions:
    """Tests for Permissions enum."""

    def test_rdonly(self):
        """Test read-only permission."""
        assert Permissions.RDONLY.value == 0

    def test_rdwr(self):
        """Test read-write permission."""
        assert Permissions.RDWR.value == 2


class TestOSType:
    """Tests for OSType enum."""

    def test_linux(self):
        """Test linux OS type."""
        assert OSType.linux.value == 0

    def test_windows(self):
        """Test windows OS type."""
        assert OSType.windows.value == 1

    def test_mac(self):
        """Test mac OS type."""
        assert OSType.mac.value == 2

    def test_os_count(self):
        """Test total OS types."""
        assert len(OSType) == 3


class TestPrivacy:
    """Tests for Privacy enum."""

    def test_public(self):
        """Test public privacy setting."""
        assert Privacy.public.value == 0

    def test_private(self):
        """Test private privacy setting."""
        assert Privacy.private.value == 1
