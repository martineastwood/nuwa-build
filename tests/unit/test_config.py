"""Unit tests for configuration parsing and validation."""

import pytest

from nuwa_build.config import (
    get_default_config,
    merge_cli_args,
    parse_nuwa_config,
    validate_config,
)


class TestDefaultConfig:
    """Tests for default configuration generation."""

    def test_default_config_basic(self):
        """Test basic default configuration values."""
        config = get_default_config("test-project")

        assert config["nim_source"] == "nim"
        assert config["module_name"] == "test_project"
        assert config["lib_name"] == "test_project_lib"
        assert config["entry_point"] == "test_project_lib.nim"
        assert config["output_location"] == "auto"
        assert config["nim_flags"] == []
        assert config["nimble_deps"] == []

    def test_module_name_from_project_name(self):
        """Test that module name is derived from project name."""
        config = get_default_config("my-awesome-project")
        assert config["module_name"] == "my_awesome_project"

    def test_lib_name_from_module_name(self):
        """Test that lib name includes _lib suffix."""
        config = get_default_config("myproject")
        assert config["lib_name"] == "myproject_lib"


class TestValidateConfig:
    """Tests for configuration validation."""

    def test_valid_config_passes(self, mock_config):
        """Test that a valid configuration passes validation."""
        # Should not raise
        validate_config(mock_config)

    def test_missing_required_field(self):
        """Test that missing required fields raise ValueError."""
        config = {
            "nim_source": "nim",
            "module_name": "test",
            # Missing "lib_name" and "entry_point"
        }

        with pytest.raises(ValueError, match="Missing required configuration fields"):
            validate_config(config)

    def test_invalid_module_name_starts_with_number(self):
        """Test that module names starting with numbers are rejected."""
        config = {
            "nim_source": "nim",
            "module_name": "123invalid",
            "lib_name": "123invalid_lib",
            "entry_point": "lib.nim",
        }

        with pytest.raises(ValueError, match="not a valid Python identifier"):
            validate_config(config)

    def test_invalid_module_name_with_hyphen(self):
        """Test that module names with hyphens are rejected."""
        # Actually, this should pass because hyphens are converted to underscores
        # But the validation should catch if it's not a valid identifier after normalization
        # For now, let's test the actual validation
        with pytest.raises(ValueError, match="not a valid Python identifier"):
            validate_config(
                {
                    "nim_source": "nim",
                    "module_name": "my package",  # Space is invalid
                    "lib_name": "my_package_lib",
                    "entry_point": "lib.nim",
                }
            )

    def test_empty_nim_source(self):
        """Test that empty nim_source is rejected."""
        config = {
            "nim_source": "",  # Empty
            "module_name": "test",
            "lib_name": "test_lib",
            "entry_point": "lib.nim",
        }

        with pytest.raises(ValueError, match="cannot be empty"):
            validate_config(config)

    @pytest.mark.parametrize(
        "module_name",
        [
            "valid_name",
            "my_module",
            "MyModule",
            "module123",
            "_private",
        ],
    )
    def test_valid_module_names(self, module_name):
        """Test that valid module names pass validation."""
        config = {
            "nim_source": "nim",
            "module_name": module_name,
            "lib_name": f"{module_name}_lib",
            "entry_point": "lib.nim",
        }
        # Should not raise
        validate_config(config)


class TestMergeCliArgs:
    """Tests for merging CLI arguments with configuration."""

    def test_merge_module_name(self, mock_config):
        """Test merging module name from CLI."""
        cli_args = {"module_name": "overridden_module"}

        result = merge_cli_args(mock_config, cli_args)

        assert result["module_name"] == "overridden_module"
        assert result["nim_source"] == "nim"  # Unchanged

    def test_merge_nim_flags(self, mock_config):
        """Test merging nim flags from CLI."""
        cli_args = {"nim_flags": ["-d:danger", "--opt:size"]}

        result = merge_cli_args(mock_config, cli_args)

        assert "-d:danger" in result["nim_flags"]
        assert "--opt:size" in result["nim_flags"]

    def test_merge_nim_flags_extends_existing(self):
        """Test that nim flags extend existing flags."""
        config = {
            "nim_source": "nim",
            "module_name": "test",
            "lib_name": "test_lib",
            "entry_point": "lib.nim",
            "nim_flags": ["--opt:speed"],
        }
        cli_args = {"nim_flags": ["-d:release"]}

        result = merge_cli_args(config, cli_args)

        assert "--opt:speed" in result["nim_flags"]
        assert "-d:release" in result["nim_flags"]

    def test_multiple_cli_overrides(self, mock_config):
        """Test merging multiple CLI arguments."""
        cli_args = {
            "module_name": "new_module",
            "nim_source": "src/nim",
            "entry_point": "main.nim",
        }

        result = merge_cli_args(mock_config, cli_args)

        assert result["module_name"] == "new_module"
        assert result["nim_source"] == "src/nim"
        assert result["entry_point"] == "main.nim"


class TestParseNuwaConfig:
    """Tests for parsing pyproject.toml."""

    def test_parse_without_pyproject(self, tmp_path):
        """Test parsing when no pyproject.toml exists."""
        import os

        original = os.getcwd()

        try:
            os.chdir(tmp_path)
            config = parse_nuwa_config()

            # Should return defaults
            assert "nim_source" in config
            assert config["nim_source"] == "nim"
        finally:
            os.chdir(original)

    def test_parse_with_minimal_config(self, temp_project):
        """Test parsing minimal pyproject.toml."""
        pyproject = temp_project / "pyproject.toml"
        pyproject.write_text(
            """[project]
name = "my-package"
version = "0.1.0"
"""
        )

        import os

        original = os.getcwd()
        try:
            os.chdir(temp_project)
            config = parse_nuwa_config()

            assert config["module_name"] == "my_package"
            assert config["lib_name"] == "my_package_lib"
        finally:
            os.chdir(original)

    def test_parse_with_custom_config(self, temp_project):
        """Test parsing custom configuration values."""
        pyproject = temp_project / "pyproject.toml"
        pyproject.write_text(
            """[project]
name = "my-package"
version = "0.1.0"

[tool.nuwa]
module-name = "custom_module"
nim-source = "src/nim"
entry-point = "main.nim"
"""
        )

        import os

        original = os.getcwd()
        try:
            os.chdir(temp_project)
            config = parse_nuwa_config()

            assert config["module_name"] == "custom_module"
            assert config["nim_source"] == "src/nim"
            assert config["entry_point"] == "main.nim"
        finally:
            os.chdir(original)
