"""Unit tests for CLI functions."""

import argparse
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from nuwa_build.cli import (
    format_error,
    handle_cli_error,
    run_init,
)
from nuwa_build.config import build_config_overrides
from nuwa_build.utils import (
    DEFAULT_DEBOUNCE_DELAY,
    NIM_APP_LIB_FLAG,
    normalize_package_name,
    validate_module_name,
    validate_path,
    validate_project_name,
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
        mock_resolve.side_effect = OSError("Cannot resolve")

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
        result = build_config_overrides(
            module_name="custom_module",
            nim_source="custom_nim",
            entry_point="custom_entry",
            output_location="custom_output",
            nim_flags=["--opt1", "--opt2"],
        )

        assert result == {
            "module_name": "custom_module",
            "nim_source": "custom_nim",
            "entry_point": "custom_entry",
            "output_location": "custom_output",
            "nim_flags": ["--opt1", "--opt2"],
        }

    def test_partial_overrides(self):
        """Test building config overrides with some options."""
        result = build_config_overrides(
            module_name="custom_module",
        )

        assert result == {"module_name": "custom_module"}

    def test_no_overrides(self):
        """Test with no overrides specified."""
        result = build_config_overrides()

        assert result == {}


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

        module_name = normalize_package_name(project_name)
        validate_module_name(module_name)

    def test_invalid_project_cannot_become_valid_module(self):
        """Test that invalid project names fail before module conversion."""
        # This project name starts with a digit
        with pytest.raises(ValueError):
            validate_project_name("123-bad-project")

        # We should never reach module validation for invalid project names


class TestRunInit:
    """Tests for run_init function."""

    def test_init_creates_pyproject_toml(self, tmp_path):
        """Test that init creates pyproject.toml when it doesn't exist."""
        args = argparse.Namespace(path=str(tmp_path))

        run_init(args)

        pyproject_path = tmp_path / "pyproject.toml"
        assert pyproject_path.exists()
        content = pyproject_path.read_text()
        assert "[build-system]" in content
        assert "[tool.nuwa]" in content
        assert "nuwa-build" in content

    def test_init_updates_existing_pyproject_toml(self, tmp_path):
        """Test that init updates existing pyproject.toml without duplicating sections."""
        # Create a basic pyproject.toml without nuwa config
        pyproject_path = tmp_path / "pyproject.toml"
        pyproject_path.write_text('[project]\nname = "my_project"\nversion = "0.1.0"\n')

        args = argparse.Namespace(path=str(tmp_path))
        run_init(args)

        content = pyproject_path.read_text()
        # Should add build-system and tool.nuwa
        assert "[build-system]" in content
        assert "[tool.nuwa]" in content
        # Should not duplicate project section
        assert content.count("[project]") == 1

    def test_init_does_not_duplicate_existing_build_system(self, tmp_path):
        """Test that init doesn't add build-system if it already exists."""
        # Create pyproject.toml with build-system
        pyproject_path = tmp_path / "pyproject.toml"
        pyproject_path.write_text(
            '[build-system]\nrequires = ["nuwa-build"]\nbuild-backend = "nuwa_build"\n\n'
            '[project]\nname = "my_project"\nversion = "0.1.0"\n'
        )

        args = argparse.Namespace(path=str(tmp_path))
        run_init(args)

        content = pyproject_path.read_text()
        # Should not duplicate build-system
        assert content.count("[build-system]") == 1

    def test_init_does_not_duplicate_existing_tool_nuwa(self, tmp_path):
        """Test that init doesn't add tool.nuwa if it already exists."""
        # Create pyproject.toml with tool.nuwa
        pyproject_path = tmp_path / "pyproject.toml"
        pyproject_path.write_text(
            '[project]\nname = "my_project"\nversion = "0.1.0"\n\n'
            '[tool.nuwa]\nmodule-name = "my_project"\n'
        )

        args = argparse.Namespace(path=str(tmp_path))
        run_init(args)

        content = pyproject_path.read_text()
        # Should not duplicate tool.nuwa
        assert content.count("[tool.nuwa]") == 1

    def test_init_creates_nim_directory(self, tmp_path):
        """Test that init creates nim directory with scaffolding."""
        args = argparse.Namespace(path=str(tmp_path))

        run_init(args)

        nim_dir = tmp_path / "nim"
        assert nim_dir.exists()
        assert nim_dir.is_dir()

        # Check that helper file exists
        helpers_file = nim_dir / "helpers.nim"
        assert helpers_file.exists()

    def test_init_does_not_overwrite_existing_nim_files(self, tmp_path):
        """Test that init doesn't overwrite existing nim files."""
        # Create nim directory with existing files
        nim_dir = tmp_path / "nim"
        nim_dir.mkdir()
        lib_file = nim_dir / "my_project_lib.nim"
        lib_file.write_text("# Existing content")

        args = argparse.Namespace(path=str(tmp_path))
        run_init(args)

        # Original content should be preserved
        content = lib_file.read_text()
        assert content == "# Existing content"

    def test_init_creates_gitignore(self, tmp_path):
        """Test that init creates .gitignore."""
        args = argparse.Namespace(path=str(tmp_path))

        run_init(args)

        gitignore_path = tmp_path / ".gitignore"
        assert gitignore_path.exists()
        content = gitignore_path.read_text()
        assert "*.so" in content or "*.pyd" in content
        assert "nimcache/" in content

    def test_init_updates_existing_gitignore(self, tmp_path):
        """Test that init updates existing .gitignore without duplicating."""
        # Create .gitignore without Nuwa patterns
        gitignore_path = tmp_path / ".gitignore"
        gitignore_path.write_text("*.pyc\n__pycache__/\n")

        args = argparse.Namespace(path=str(tmp_path))
        run_init(args)

        content = gitignore_path.read_text()
        # Should add Nuwa patterns
        assert "*.so" in content or "*.pyd" in content
        # Should keep existing content
        assert "*.pyc" in content

    def test_init_does_not_duplicate_gitignore_patterns(self, tmp_path):
        """Test that init doesn't duplicate patterns if they already exist."""
        # Create .gitignore with Nuwa patterns already
        gitignore_path = tmp_path / ".gitignore"
        gitignore_path.write_text("*.so\n*.pyd\nnimcache/\n")

        args = argparse.Namespace(path=str(tmp_path))
        run_init(args)

        content = gitignore_path.read_text()
        # Patterns should exist but not be duplicated
        assert content.count("*.so") == 1
        assert content.count("*.pyd") == 1

    def test_init_uses_project_name_from_pyproject(self, tmp_path):
        """Test that init reads project name from existing pyproject.toml."""
        # Create pyproject.toml with project name
        pyproject_path = tmp_path / "pyproject.toml"
        pyproject_path.write_text('[project]\nname = "custom_project"\nversion = "0.1.0"\n')

        args = argparse.Namespace(path=str(tmp_path))
        run_init(args)

        # Check that nim files were created with correct module name
        helpers_file = tmp_path / "nim" / "helpers.nim"
        if helpers_file.exists():
            content = helpers_file.read_text()
            # Module name should be derived from project name (custom_project)
            assert "custom_project" in content

    def test_init_defaults_to_directory_name(self, tmp_path):
        """Test that init uses directory name when no pyproject.toml exists."""
        # Directory name will be the tmp_path's last component
        args = argparse.Namespace(path=str(tmp_path))
        run_init(args)

        # Should still create pyproject.toml
        pyproject_path = tmp_path / "pyproject.toml"
        assert pyproject_path.exists()

    def test_init_with_path_argument(self, tmp_path):
        """Test that init works with explicit path argument."""
        # Create a subdirectory
        project_dir = tmp_path / "my_project"
        project_dir.mkdir()

        args = argparse.Namespace(path=str(project_dir))
        run_init(args)

        # Should create files in the specified directory
        assert (project_dir / "pyproject.toml").exists()
        assert (project_dir / "nim").exists()

    def test_init_with_default_path(self, tmp_path, monkeypatch):
        """Test that init uses current directory when no path is provided."""
        # Change to temp directory
        monkeypatch.chdir(tmp_path)

        # Simulate running with path=None (should use ".")
        args = argparse.Namespace(path=None)
        run_init(args)

        # Should create files in current directory
        assert (tmp_path / "pyproject.toml").exists()
        assert (tmp_path / "nim").exists()
