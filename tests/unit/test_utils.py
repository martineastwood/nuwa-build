"""Unit tests for utility functions."""

import subprocess
from unittest.mock import patch

import pytest

from nuwa_build.utils import (
    check_nim_installed,
    check_nimble_installed,
    get_platform_extension,
    get_wheel_tags,
    temp_directory,
    working_directory,
)


class TestGetPlatformExtension:
    """Tests for platform-specific extension."""

    def test_uses_sysconfig_ext_suffix(self):
        """Test that sysconfig EXT_SUFFIX is used when available."""
        with patch("nuwa_build.utils.sysconfig.get_config_var") as mock_sysconfig:
            mock_sysconfig.return_value = ".cpython-310-x86_64-linux-gnu.so"
            assert get_platform_extension() == ".cpython-310-x86_64-linux-gnu.so"
            mock_sysconfig.assert_called_once_with("EXT_SUFFIX")

    def test_fallback_to_hardcoded_extensions(self):
        """Test fallback when sysconfig returns None."""
        with (
            patch("nuwa_build.utils.sysconfig.get_config_var") as mock_sysconfig,
            patch("sys.platform", "win32"),
        ):
            mock_sysconfig.return_value = None
            assert get_platform_extension() == ".pyd"

        with (
            patch("nuwa_build.utils.sysconfig.get_config_var") as mock_sysconfig,
            patch("sys.platform", "linux"),
        ):
            mock_sysconfig.return_value = None
            assert get_platform_extension() == ".so"

    def test_windows_extension(self):
        """Test Windows-specific extension."""
        with patch(
            "nuwa_build.utils.sysconfig.get_config_var",
            return_value=".cpython-310-win_amd64.pyd",
        ):
            assert get_platform_extension() == ".cpython-310-win_amd64.pyd"

    def test_darwin_extension(self):
        """Test macOS-specific extension."""
        with patch(
            "nuwa_build.utils.sysconfig.get_config_var",
            return_value=".cpython-310-darwin.so",
        ):
            assert get_platform_extension() == ".cpython-310-darwin.so"


class TestCheckNimInstalled:
    """Tests for Nim compiler detection."""

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_nim_found(self, mock_run, mock_which):
        """Test when Nim is found in PATH."""
        mock_which.return_value = "/usr/bin/nim"
        mock_run.return_value = None  # Successful version check

        # Should not raise
        check_nim_installed()

        mock_which.assert_called_with("nim")
        mock_run.assert_called_once()

    @patch("shutil.which")
    def test_nim_not_found(self, mock_which):
        """Test when Nim is not found in PATH."""
        mock_which.return_value = None

        with pytest.raises(RuntimeError, match="Nim compiler not found"):
            check_nim_installed()

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_nim_not_working(self, mock_run, mock_which):
        """Test when Nim exists but doesn't work."""
        mock_which.return_value = "/usr/bin/nim"
        mock_run.side_effect = subprocess.CalledProcessError(
            1, ["nim", "--version"], stderr="Nim is broken"
        )

        with pytest.raises(RuntimeError, match="not working"):
            check_nim_installed()


class TestGetWheelTags:
    """Tests for wheel tag generation."""

    def test_wheel_tags_format(self):
        """Test wheel tag format using packaging.tags.

        This test verifies that get_wheel_tags() produces valid wheel filenames
        with proper Python, ABI, and platform tags. Since packaging.tags.sys_tags()
        returns the actual tags for the current system, we verify the format
        structure rather than specific values.
        """
        result = get_wheel_tags("mypackage", "1.0.0")

        # Should be in format: {name}-{version}-{python}-{abi}-{platform}.whl
        assert result.startswith("mypackage-1.0.0-")
        assert result.endswith(".whl")

        # Split and verify we have 5 parts total
        parts = result[:-4].split("-")  # Remove .whl and split
        assert len(parts) == 5, f"Expected 5 parts, got {len(parts)}: {parts}"

        # Verify structure: name, version, python_tag, abi_tag, platform_tag
        assert parts[0] == "mypackage"
        assert parts[1] == "1.0.0"

        # Python tag should start with 'cp' for CPython or 'py' for PyPy
        python_tag = parts[2]
        assert python_tag.startswith(("cp", "py")), f"Invalid Python tag: {python_tag}"

        # ABI tag should be valid (e.g., 'cp310', 'cp314t', 'abi3', 'none')
        abi_tag = parts[3]
        assert abi_tag.startswith(("cp", "abi", "none")), f"Invalid ABI tag: {abi_tag}"

        # Platform tag should be valid (e.g., 'macosx', 'linux', 'win')
        platform_tag = parts[4]
        assert platform_tag, f"Invalid platform tag: {platform_tag}"

    def test_wheel_tags_normalizes_package_name(self):
        """Test that package names are normalized (hyphens -> underscores)."""
        result = get_wheel_tags("my-package", "1.0.0")

        # Wheel filenames must use underscores
        assert "my_package-1.0.0" in result
        assert "my-package" not in result


class TestCheckNimbleInstalled:
    """Tests for Nimble detection."""

    @patch("shutil.which")
    def test_nimble_found(self, mock_which):
        """Test when Nimble is found."""
        mock_which.return_value = "/usr/bin/nimble"

        assert check_nimble_installed() is True

    @patch("shutil.which")
    def test_nimble_not_found(self, mock_which):
        """Test when Nimble is not found."""
        mock_which.return_value = None

        assert check_nimble_installed() is False


class TestTempDirectory:
    """Tests for temp_directory context manager."""

    def test_creates_and_removes_directory(self):
        """Test that directory is created and cleaned up."""
        with temp_directory() as temp_dir:
            assert temp_dir.exists()
            # Create a test file
            (temp_dir / "test.txt").write_text("test")

        # Directory should be removed
        assert not temp_dir.exists()

    def test_cleans_up_on_exception(self):
        """Test that directory is cleaned up even on exception."""
        temp_dir = None

        try:
            with temp_directory() as td:
                temp_dir = td
                raise ValueError("Test exception")
        except ValueError:
            pass

        # Should still be cleaned up
        assert temp_dir is not None
        assert not temp_dir.exists()


class TestWorkingDirectory:
    """Tests for working_directory context manager."""

    def test_changes_and_restores_directory(self, tmp_path):
        """Test that directory is changed and restored."""
        import os

        original = os.getcwd()

        with working_directory(tmp_path):
            assert os.getcwd() == str(tmp_path)

        # Should be restored
        assert os.getcwd() == original

    def test_restores_on_exception(self, tmp_path):
        """Test that directory is restored even on exception."""
        import os

        original = os.getcwd()

        try:
            with working_directory(tmp_path):
                raise ValueError("Test exception")
        except ValueError:
            pass

        # Should still be restored
        assert os.getcwd() == original
