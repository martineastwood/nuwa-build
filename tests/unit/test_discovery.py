"""Unit tests for source file discovery."""

import pytest

from nuwa_build.discovery import (
    discover_entry_point_fallback,
    validate_nim_entry_point,
)


class TestEntryPointFallback:
    """Tests for entry point fallback discovery logic."""

    @pytest.fixture
    def nim_dir(self, tmp_path):
        """Create a temporary Nim directory."""
        nim_dir = tmp_path / "nim"
        nim_dir.mkdir()
        return nim_dir

    def test_discovers_module_lib_nim(self, nim_dir):
        """Test discovery of {module_name}_lib.nim pattern."""
        # Create the expected file
        (nim_dir / "test_module_lib.nim").write_text("import nimpy")

        module_name = "test_module"

        result_dir, result_file = discover_entry_point_fallback(nim_dir, module_name)

        assert result_dir == nim_dir
        assert result_file == nim_dir / "test_module_lib.nim"

    def test_discovers_lib_nim(self, nim_dir):
        """Test discovery of lib.nim fallback pattern."""
        # Create lib.nim
        (nim_dir / "lib.nim").write_text("import nimpy")

        result_dir, result_file = discover_entry_point_fallback(nim_dir, "test_module")

        assert result_file == nim_dir / "lib.nim"

    def test_single_file_fallback(self, nim_dir):
        """Test discovery when only one .nim file exists."""
        # Create single file with different name
        (nim_dir / "main.nim").write_text("import nimpy")

        result_dir, result_file = discover_entry_point_fallback(nim_dir, "test_module")

        assert result_file == nim_dir / "main.nim"

    def test_error_on_multiple_files(self, nim_dir):
        """Test that multiple files without clear entry point raises error."""
        # Create multiple .nim files
        (nim_dir / "file1.nim").write_text("")
        (nim_dir / "file2.nim").write_text("")

        with pytest.raises(ValueError, match="Multiple .nim files found"):
            discover_entry_point_fallback(nim_dir, "test_module")

    def test_error_on_no_files(self, nim_dir):
        """Test that no .nim files raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="No .nim files found"):
            discover_entry_point_fallback(nim_dir, "test_module")


class TestValidateNimEntryPoint:
    """Tests for Nim entry point validation."""

    @pytest.fixture
    def nim_dir(self, tmp_path):
        """Create a temporary Nim directory."""
        nim_dir = tmp_path / "nim"
        nim_dir.mkdir()
        return nim_dir

    def test_valid_entry_point(self, nim_dir):
        """Test validation of a valid entry point."""
        # Create entry point
        entry = nim_dir / "test_lib.nim"
        entry.write_text("import nimpy")

        # Should not raise
        validate_nim_entry_point(entry)

    def test_missing_entry_point(self, nim_dir):
        """Test that missing entry point raises error."""
        entry = nim_dir / "nonexistent.nim"

        with pytest.raises(FileNotFoundError, match="Entry point not found"):
            validate_nim_entry_point(entry)


class TestDiscoverNimSources:
    """Tests for source discovery with config."""

    @pytest.fixture
    def nim_dir(self, tmp_path):
        """Create a temporary Nim directory."""
        nim_dir = tmp_path / "nim"
        nim_dir.mkdir()
        return nim_dir

    def test_discovers_explicit_entry_point(self, nim_dir):
        """Test discovery with explicit entry_point in config."""
        # Create entry point
        (nim_dir / "main.nim").write_text("import nimpy")

        config = {
            "nim_source": str(nim_dir),
            "module_name": "test",
            "lib_name": "test_lib",
            "entry_point": "main.nim",
        }

        from nuwa_build.discovery import discover_nim_sources

        result_dir, result_file = discover_nim_sources(config)

        assert result_dir == nim_dir
        assert result_file == nim_dir / "main.nim"

    def test_falls_back_to_auto_discovery(self, nim_dir):
        """Test fallback when explicit entry_point doesn't exist."""
        # Create fallback file
        (nim_dir / "test_lib.nim").write_text("import nimpy")

        config = {
            "nim_source": str(nim_dir),
            "module_name": "test",
            "lib_name": "test_lib",
            "entry_point": "nonexistent.nim",  # Doesn't exist
        }

        from nuwa_build.discovery import discover_nim_sources

        result_dir, result_file = discover_nim_sources(config)

        # Should fall back to discover_entry_point_fallback
        assert result_file == nim_dir / "test_lib.nim"
