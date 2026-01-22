"""Unit tests for configuration parsing and validation."""


from nuwa_build.config import (
    merge_cli_args,
    parse_nuwa_config,
)


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
