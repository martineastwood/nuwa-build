"""Error parsing and formatting for Nim compiler output."""

import re
import subprocess
from pathlib import Path
from typing import Optional


def format_error(error: Exception) -> str:
    """Format an exception with consistent error message style.

    Args:
        error: The exception to format

    Returns:
        Formatted error message string
    """
    error_type = type(error).__name__

    if isinstance(error, FileNotFoundError):
        return f"❌ Error: {error}"
    elif isinstance(error, ValueError):
        return f"❌ Configuration Error: {error}"
    elif isinstance(error, subprocess.CalledProcessError):
        # Error already formatted and printed by backend.py
        return ""
    elif isinstance(error, RuntimeError):
        return f"❌ Error: {error}"
    elif isinstance(error, OSError):
        return f"❌ System Error: {error}"
    else:
        return f"❌ Unexpected Error ({error_type}): {error}"


def parse_nim_error(stderr: str) -> Optional[dict]:
    """Parse a Nim compiler error into structured format.

    Args:
        stderr: Raw stderr output from Nim compiler

    Returns:
        Dictionary with error details, or None if no error found
    """
    lines = stderr.strip().split("\n")

    # Nim error format: "filename(line, col) Error: message"
    # or "filename(line, col) Hint: message"
    # Also handles spaces around comma: "filename(line , col ) Error: message"
    error_pattern = re.compile(r"^(.+)\((\d+)\s*,\s*(\d+)\s*\)\s+(Error|Warning|Hint):\s+(.+)$")

    for line in lines:
        match = error_pattern.match(line.strip())
        if match:
            return {
                "file": match.group(1),
                "line": int(match.group(2)),
                "col": int(match.group(3)),
                "level": match.group(4),  # Error, Warning, Hint
                "message": match.group(5).strip(),
            }

    return None


def get_error_context(
    file_path: Path, line_num: int, context_lines: int = 2
) -> tuple[list[str], int]:
    """Get source code context around an error.

    Args:
        file_path: Path to the source file
        line_num: Line number where error occurred
        context_lines: Number of lines to show before and after

    Returns:
        Tuple of (list of context lines, index of error line in context)
    """
    try:
        with open(file_path, encoding="utf-8") as f:
            lines = f.readlines()

        start = max(0, line_num - context_lines - 1)
        end = min(len(lines), line_num + context_lines)

        context = lines[start:end]
        error_index = line_num - start - 1

        # Add line numbers
        numbered_context = []
        for i, line in enumerate(context):
            line_no = start + i + 1
            marker = " > " if i == error_index else "   "
            numbered_context.append(f"{line_no:4d}{marker}{line.rstrip()}")

        return numbered_context, error_index
    except Exception:
        return [], 0


ERROR_SUGGESTIONS = {
    # Type errors
    "type mismatch": [
        "Check that argument types match the function signature",
        "Use $() to convert to string: $(myInt)",
        "Use int() to convert string to int: int(myString)",
    ],
    # Undeclared identifiers
    "undeclared": [
        "Check for typos in the identifier name",
        "Make sure the variable is defined before use",
        "Import the module if it's defined elsewhere",
    ],
    # Missing imports
    "cannot open": [
        "Ensure the file exists in the project directory",
        "Check the file name and path are correct",
        "Make sure you're using 'include' for shared libraries, not 'import'",
    ],
    # Module issues
    "module": [
        "Ensure the module is in your Nim path",
        "Check that all 'include'd files exist",
    ],
    # Nuwa SDK specific
    "nuwa_sdk": [
        "Install nimble package: nimble install nuwa_sdk",
        "Import nuwa_sdk: import nuwa_sdk",
        "Make sure proc has {.nuwa_export.} pragma",
    ],
    # Nuwa export/pragma errors
    "nuwa_export": [
        "Make sure you imported nuwa_sdk: import nuwa_sdk",
        "Install nimble package: nimble install nuwa_sdk",
        "The {.nuwa_export.} pragma requires the nuwa_sdk module",
    ],
    # Legacy exportpy (for backward compatibility with error messages)
    "exportpy": [
        "Consider using {.nuwa_export.} instead (requires nuwa_sdk)",
        "Install nimble package: nimble install nuwa_sdk",
        "Import nuwa_sdk: import nuwa_sdk",
    ],
    "pragma": [
        "Check that the pragma name is spelled correctly",
        "Some pragmas require importing specific modules",
    ],
    # Syntax errors
    "expected": [
        "Check for missing parentheses, brackets, or braces",
        "Ensure proper indentation",
        "Check that statements are separated correctly",
    ],
}


def get_suggestions(error_message: str) -> list[str]:
    """Get helpful suggestions based on error message.

    Args:
        error_message: The error message text

    Returns:
        List of suggestion strings
    """
    suggestions = []
    error_lower = error_message.lower()

    for keyword, tips in ERROR_SUGGESTIONS.items():
        if keyword.lower() in error_lower:
            suggestions.extend(tips)

    return suggestions


def format_compilation_error(stderr: str, working_dir: Optional[Path] = None) -> str:
    """Format Nim compiler error with context and suggestions.

    Args:
        stderr: Raw stderr from Nim compiler
        working_dir: Working directory for resolving file paths

    Returns:
        Formatted error message
    """
    error = parse_nim_error(stderr)

    if not error:
        # Fallback: return raw output if we can't parse it
        return stderr

    # Resolve file path
    file_path = Path(error["file"])
    if working_dir and not file_path.is_absolute():
        file_path = working_dir / file_path

    # Build formatted error
    output = []

    # Header
    symbol = "❌" if error["level"] == "Error" else "⚠️"
    output.append(f"\n{symbol} {error['level']} in {file_path}")
    output.append(f"   Line {error['line']}, Column {error['col']}")
    output.append("")

    # Error message
    output.append(f"Message: {error['message']}")
    output.append("")

    # Context
    context_lines, error_idx = get_error_context(file_path, error["line"])
    if context_lines:
        output.append("Code:")
        output.append("```nim")
        output.extend(context_lines)
        output.append("```")
        output.append("")

    # Suggestions
    suggestions = get_suggestions(error["message"])
    if suggestions:
        output.append("💡 Suggestions:")
        for i, suggestion in enumerate(suggestions, 1):
            output.append(f"  {i}. {suggestion}")
        output.append("")

    # Full compiler output (for debugging)
    output.append("--- Full compiler output ---")
    output.append(stderr)

    return "\n".join(output)


def format_compilation_success(output_path: Path) -> str:
    """Format successful compilation message.

    Args:
        output_path: Path to compiled extension

    Returns:
        Formatted success message
    """
    size = output_path.stat().st_size
    size_mb = size / (1024 * 1024)

    return f"✅ Built {output_path.name} ({size_mb:.2f} MB)"
