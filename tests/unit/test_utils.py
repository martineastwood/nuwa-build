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


class TestCheckNimInstalled:
    """Tests for Nim compiler detection."""

    @patch("shutil.which")
    def test_nim_found(self, mock_which):
        """Test when Nim is found in PATH."""
        mock_which.return_value = "/usr/bin/nim"

        # Should not raise
        check_nim_installed()

        mock_which.assert_called_with("nim")

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


class TestGetPlatformExtension:
    """Tests for platform-specific extension."""

    @pytest.mark.parametrize(
        "platform,expected",
        [
            ("win32", ".pyd"),
            ("linux", ".so"),
            ("darwin", ".so"),
        ],
    )
    def test_platform_extensions(self, platform, expected):
        """Test extension for different platforms."""
        with patch("sys.platform", platform):
            assert get_platform_extension() == expected


class TestGetWheelTags:
    """Tests for wheel tag generation."""

    @patch("sysconfig.get_config_var")
    @patch("sysconfig.get_platform")
    def test_wheel_tags_format(self, mock_platform, mock_config_var):
        """Test wheel tag format."""
        mock_config_var.return_value = "cpython-310-x86_64-linux-gnu"
        mock_platform.return_value = "linux-x86_64"

        result = get_wheel_tags("mypackage", "1.0.0")

        # Should be: mypackage-1.0.0-cp-cp310-cpython-310-x86_64-linux-gnu.whl
        assert "mypackage-1.0.0" in result
        assert ".whl" in result
        # The SOABI contains "cp310" in the middle
        assert "310" in result


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
