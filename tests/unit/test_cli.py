"""Unit tests for CLI functions."""

import argparse
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from nuwa_build.cli import (
    build_config_overrides,
    format_error,
    handle_cli_error,
    validate_module_name,
    validate_path,
    validate_project_name,
)
from nuwa_build.constants import (
    DEFAULT_DEBOUNCE_DELAY,
    NIM_APP_LIB_FLAG,
    SHARED_LIBRARY_PERMISSIONS,
)


class TestValidateProjectName:
    """Tests for validate_project_name function."""

    def test_valid_names(self):
        """Test that valid project names are accepted."""
        valid_names = [
            "myproject",
            "my_project",
            "my-project",
            "MyProject",
            "project123",
        ]
        for name in valid_names:
            # Should not raise
            validate_project_name(name)

    def test_empty_name(self):
        """Test that empty name is rejected."""
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_project_name("")

    def test_name_too_long(self):
        """Test that name over 100 characters is rejected."""
        long_name = "a" * 101
        with pytest.raises(ValueError, match="too long"):
            validate_project_name(long_name)

    def test_invalid_characters(self):
        """Test that names with invalid characters are rejected."""
        invalid_names = [
            "my project",  # space
            "my.project",  # dot
            "my/project",  # slash
            "my@project",  # at sign
        ]
        for name in invalid_names:
            with pytest.raises(ValueError, match="can only contain"):
                validate_project_name(name)

    def test_starts_with_digit(self):
        """Test that names starting with digit are rejected."""
        with pytest.raises(ValueError, match="must start with"):
            validate_project_name("123project")

    def test_starts_with_hyphen(self):
        """Test that names starting with hyphen are rejected."""
        with pytest.raises(ValueError, match="must start with"):
            validate_project_name("-project")

    def test_python_keyword_conflict(self):
        """Test that Python keyword conflicts are detected."""
        # These are normalized to module names
        with (
            patch("nuwa_build.cli.sys.modules", {"import": MagicMock()}),
            pytest.raises(ValueError, match="conflicts"),
        ):
            validate_project_name("import")  # becomes "import" module

    def test_python_builtin_conflict(self):
        """Test that Python builtin conflicts are detected."""
        # 'print' is already a real builtin, so no mocking needed
        with pytest.raises(ValueError, match="conflicts"):
            validate_project_name("print")  # becomes "print" module


class TestValidateModuleName:
    """Tests for validate_module_name function."""

    def test_valid_module_names(self):
        """Test that valid module names are accepted."""
        valid_names = ["my_module", "my_module2", "_private", "MyModule"]
        for name in valid_names:
            # Should not raise
            validate_module_name(name)

    def test_empty_name(self):
        """Test that empty name is rejected."""
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_module_name("")

    def test_starts_with_digit(self):
        """Test that module names starting with digit are rejected."""
        with pytest.raises(ValueError, match="not a valid Python identifier"):
            validate_module_name("123module")

    def test_invalid_characters(self):
        """Test that invalid characters are rejected."""
        invalid_names = [
            "my-module",  # hyphen
            "my module",  # space
            "my.module",  # dot
        ]
        for name in invalid_names:
            with pytest.raises(ValueError, match="not a valid Python identifier"):
                validate_module_name(name)

    def test_hyphen_normalized_from_project_name(self):
        """Test that hyphens in project names are normalized to underscores."""
        # This should pass (my-project -> my_module)
        validate_module_name("my_module")


class TestValidatePath:
    """Tests for validate_path function."""

    def test_valid_relative_path(self, tmp_path):
        """Test that valid relative paths are accepted."""
        # Create parent directory
        parent = tmp_path / "projects"
        parent.mkdir()

        # Should not raise
        validate_path(parent / "newproject")

    def test_nonexistent_parent(self):
        """Test that path with nonexistent parent is rejected."""
        with pytest.raises(ValueError, match="Parent directory does not exist"):
            validate_path(Path("/nonexistent/dir/project"))

    @patch("pathlib.Path.resolve")
    def test_invalid_path_resolution(self, mock_resolve):
        """Test handling of invalid path that cannot be resolved."""
        mock_resolve.side_effect = Exception("Cannot resolve")

        with pytest.raises(ValueError, match="Invalid path"):
            validate_path(Path("invalid\x00path"))

    def test_absolute_path_warning(self, tmp_path, capsys):
        """Test that absolute paths generate a warning."""
        validate_path(tmp_path / "project")

        captured = capsys.readouterr()
        assert "Warning: Using absolute path" in captured.out


class TestBuildConfigOverrides:
    """Tests for build_config_overrides function."""

    def test_all_overrides(self):
        """Test building config overrides with all options."""
        args = argparse.Namespace(
            module_name="custom_module",
            nim_source="custom_nim",
            entry_point="custom_entry",
            output_dir="custom_output",
            nim_flags=["--opt1", "--opt2"],
        )

        result = build_config_overrides(args)

        assert result == {
            "module_name": "custom_module",
            "nim_source": "custom_nim",
            "entry_point": "custom_entry",
            "output_location": "custom_output",
            "nim_flags": ["--opt1", "--opt2"],
        }

    def test_partial_overrides(self):
        """Test building config overrides with some options."""
        args = argparse.Namespace(
            module_name="custom_module",
            nim_source=None,
            entry_point=None,
            output_dir=None,
            nim_flags=None,
        )

        result = build_config_overrides(args)

        assert result == {"module_name": "custom_module"}

    def test_no_overrides(self):
        """Test with no overrides specified."""
        args = argparse.Namespace(
            module_name=None,
            nim_source=None,
            entry_point=None,
            output_dir=None,
            nim_flags=None,
        )

        result = build_config_overrides(args)

        assert result is None


class TestFormatError:
    """Tests for format_error function."""

    def test_file_not_found_error(self):
        """Test formatting FileNotFoundError."""
        error = FileNotFoundError("test.txt not found")
        result = format_error(error)
        assert result == "❌ Error: test.txt not found"

    def test_value_error(self):
        """Test formatting ValueError."""
        error = ValueError("invalid value")
        result = format_error(error)
        assert result == "❌ Configuration Error: invalid value"

    def test_runtime_error(self):
        """Test formatting RuntimeError."""
        error = RuntimeError("runtime issue")
        result = format_error(error)
        assert result == "❌ Error: runtime issue"

    def test_os_error(self):
        """Test formatting OSError."""
        error = OSError("system error")
        result = format_error(error)
        assert result == "❌ System Error: system error"

    def test_generic_exception(self):
        """Test formatting generic exception."""
        error = Exception("unexpected error")
        result = format_error(error)
        assert result == "❌ Unexpected Error (Exception): unexpected error"

    def test_called_process_error(self):
        """Test formatting CalledProcessError (should return empty string)."""
        error = subprocess.CalledProcessError(1, "nim")
        result = format_error(error)
        assert result == ""


class TestHandleCliError:
    """Tests for handle_cli_error function."""

    def test_exits_with_code_1(self):
        """Test that handle_cli_error exits with code 1."""
        error = ValueError("test error")
        with pytest.raises(SystemExit) as exc_info:
            handle_cli_error(error)
        assert exc_info.value.code == 1

    def test_prints_error_message(self, capsys):
        """Test that error message is printed."""
        error = ValueError("test error")
        with pytest.raises(SystemExit):
            handle_cli_error(error)

        captured = capsys.readouterr()
        assert "Configuration Error" in captured.out

    def test_logs_unexpected_errors(self, caplog):
        """Test that unexpected errors are logged with traceback."""

        error = Exception("unexpected")
        with pytest.raises(SystemExit):
            handle_cli_error(error, context="Test context")

        # Check that error was logged
        assert any("Test context" in record.message for record in caplog.records)


class TestConstants:
    """Tests for constants."""

    def test_nim_app_lib_flag(self):
        """Test NIM_APP_LIB_FLAG constant."""
        assert NIM_APP_LIB_FLAG == "--app:lib"
        assert isinstance(NIM_APP_LIB_FLAG, str)

    def test_shared_library_permissions(self):
        """Test SHARED_LIBRARY_PERMISSIONS constant."""
        assert SHARED_LIBRARY_PERMISSIONS == 0o100755 << 16
        assert isinstance(SHARED_LIBRARY_PERMISSIONS, int)

    def test_default_debounce_delay(self):
        """Test DEFAULT_DEBOUNCE_DELAY constant."""
        assert DEFAULT_DEBOUNCE_DELAY == 0.5
        assert isinstance(DEFAULT_DEBOUNCE_DELAY, (int, float))


class TestValidationIntegration:
    """Integration tests for validation functions."""

    def test_project_to_module_validation_chain(self):
        """Test that project name validation leads to valid module name."""
        project_name = "my-awesome-project"
        validate_project_name(project_name)

        module_name = project_name.replace("-", "_")
        validate_module_name(module_name)

    def test_invalid_project_cannot_become_valid_module(self):
        """Test that invalid project names fail before module conversion."""
        # This project name starts with a digit
        with pytest.raises(ValueError):
            validate_project_name("123-bad-project")

        # We should never reach module validation for invalid project names
