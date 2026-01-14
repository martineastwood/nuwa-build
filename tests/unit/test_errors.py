"""Unit tests for error parsing and formatting."""

import pytest
from pathlib import Path
from nuwa_build.errors import (
    parse_nim_error,
    get_error_context,
    get_suggestions,
    format_compilation_error,
    format_compilation_success,
)


class TestParseNimError:
    """Tests for parsing Nim compiler errors."""

    def test_parse_error_with_file_line_col(self):
        """Test parsing error with file, line, and column."""
        stderr = "hint.nim(12, 10) Error: type mismatch"

        result = parse_nim_error(stderr)

        assert result is not None
        assert result["file"] == "hint.nim"
        assert result["line"] == 12
        assert result["col"] == 10
        assert result["level"] == "Error"
        assert result["message"] == "type mismatch"

    def test_parse_warning(self):
        """Test parsing a warning."""
        stderr = "hint.nim(12, 10) Hint: add 'exportpy' pragma"

        result = parse_nim_error(stderr)

        assert result["level"] == "Hint"
        assert result["message"] == "add 'exportpy' pragma"

    def test_parse_multiline_stderr(self):
        """Test parsing when stderr has multiple lines."""
        stderr = """Hint: config file loaded
hint.nim(12, 10) Error: type mismatch
Compilation failed"""

        result = parse_nim_error(stderr)

        assert result is not None
        assert result["message"] == "type mismatch"

    def test_parse_returns_none_for_invalid_format(self):
        """Test that invalid format returns None."""
        stderr = "This is not a valid Nim error format"

        result = parse_nim_error(stderr)

        assert result is None

    def test_parse_with_spaces_around_comma(self):
        """Test parsing with spaces around comma."""
        stderr = "hint.nim(12 , 10 ) Error: type mismatch"

        result = parse_nim_error(stderr)

        assert result is not None
        assert result["line"] == 12
        assert result["col"] == 10


class TestGetErrorContext:
    """Tests for getting source code context."""

    def test_get_context_from_file(self, tmp_path):
        """Test getting context from an actual file."""
        # Create test file
        test_file = tmp_path / "test.nim"
        test_file.write_text("""line 1
line 2
line 3
line 4
line 5
""")

        context, error_idx = get_error_context(test_file, 3, context_lines=2)

        assert len(context) == 5  # 2 before + line + 2 after
        assert error_idx == 2  # 0-indexed, so line 3 is at index 2

    def test_get_context_near_file_start(self, tmp_path):
        """Test getting context when error is near file start."""
        test_file = tmp_path / "test.nim"
        test_file.write_text("""line 1
line 2
line 3
""")

        context, error_idx = get_error_context(test_file, 1, context_lines=2)

        # Should only return lines that exist
        assert len(context) >= 1
        assert error_idx >= 0

    def test_get_context_handles_missing_file(self):
        """Test that missing file returns empty context."""
        context, error_idx = get_error_context(Path("/nonexistent/file.nim"), 5)

        assert context == []
        assert error_idx == 0


class TestGetSuggestions:
    """Tests for getting error suggestions."""

    def test_type_mismatch_suggestions(self):
        """Test suggestions for type mismatch errors."""
        suggestions = get_suggestions("type mismatch: got 'int' but expected 'string'")

        assert len(suggestions) > 0
        assert any("$()" in s for s in suggestions)
        assert any("int()" in s for s in suggestions)

    def test_undeclared_suggestions(self):
        """Test suggestions for undeclared identifier errors."""
        suggestions = get_suggestions("undeclared identifier: 'myVar'")

        assert len(suggestions) > 0
        assert any("typos" in s.lower() for s in suggestions)

    def test_exportpy_suggestions(self):
        """Test suggestions for exportpy pragma errors."""
        suggestions = get_suggestions("invalid pragma: exportpy")

        assert len(suggestions) > 0
        assert any("nimpy" in s.lower() for s in suggestions)
        assert any("import" in s.lower() for s in suggestions)

    def test_no_suggestions_for_unknown_error(self):
        """Test that unknown errors return empty list."""
        suggestions = get_suggestions("some completely unknown error message")

        assert suggestions == []


class TestFormatCompilationError:
    """Tests for error formatting."""

    def test_format_error_with_context(self, tmp_path):
        """Test formatting error with file context."""
        # Create test file with error
        test_file = tmp_path / "test.nim"
        test_file.write_text("""proc test(): string =
  return 123
""")

        stderr = "test.nim(2, 10) Error: type mismatch"

        result = format_compilation_error(stderr, working_dir=tmp_path)

        assert "❌ Error in" in result
        assert "Line 2" in result
        assert "Code:" in result
        assert "return 123" in result

    def test_format_includes_suggestions(self):
        """Test that formatted error includes suggestions."""
        stderr = "test.nim(5, 10) Error: type mismatch"

        result = format_compilation_error(stderr)

        assert "💡 Suggestions:" in result

    def test_format_includes_full_output(self):
        """Test that full compiler output is included."""
        stderr = "test.nim(5, 10) Error: type mismatch"

        result = format_compilation_error(stderr)

        assert "--- Full compiler output ---" in result
        assert stderr in result


class TestFormatCompilationSuccess:
    """Tests for success message formatting."""

    def test_format_success_with_size(self, tmp_path):
        """Test that success message includes file size."""
        # Create a test file
        test_file = tmp_path / "test_lib.so"
        test_file.write_text("x" * 100000)  # 100KB

        result = format_compilation_success(test_file)

        assert "✅ Built test_lib.so" in result
        # Should show size in MB or KB
        assert "MB" in result or "KB" in result

    def test_format_success_small_file(self, tmp_path):
        """Test formatting for small files (< 1 MB)."""
        test_file = tmp_path / "test_lib.so"
        test_file.write_text("x" * 50000)  # 50KB

        result = format_compilation_success(test_file)

        assert "0.0" in result  # Small file
        assert "MB" in result
