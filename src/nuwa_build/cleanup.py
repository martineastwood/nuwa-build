"""Build artifact cleanup functionality for Nuwa Build."""

import shutil
from pathlib import Path
from typing import Optional

from .config import parse_nuwa_config
from .utils import get_platform_extension

# Directories to clean with their display names
DIRECTORIES_TO_CLEAN = {
    ".nimble": ".nimble/",
    "nimcache": "nimcache/",
    ".nuwacache": ".nuwacache/",
    "build": "build/",
    "dist": "dist/",
}


def _safe_remove_dir(path: Path, name: str) -> tuple[list[str], list[str]]:
    """Safely remove a directory if it exists.

    Args:
        path: Path to directory
        name: Display name for the directory

    Returns:
        Tuple of (cleaned_items, error_messages)
    """
    cleaned: list[str] = []
    errors: list[str] = []

    if path.exists() and path.is_dir():
        try:
            shutil.rmtree(path)
            cleaned.append(name)
        except OSError as e:
            errors.append(f"{name}: {e}")

    return cleaned, errors


def _safe_remove_file(path: Path, project_root: Path) -> tuple[list[str], list[str]]:
    """Safely remove a file if it exists and is not a symlink.

    Args:
        path: Path to file
        project_root: Project root directory for relative paths

    Returns:
        Tuple of (cleaned_items, error_messages)
    """
    cleaned: list[str] = []
    errors: list[str] = []

    if path.exists() and path.is_file():
        # Skip symlinks to avoid deleting the target
        if path.is_symlink():
            return cleaned, errors

        try:
            path.unlink()
            # Try to get relative path, fall back to absolute if it fails
            try:
                display_path = str(path.relative_to(project_root))
            except ValueError:
                display_path = str(path)
            cleaned.append(display_path)
        except OSError as e:
            errors.append(f"{path}: {e}")

    return cleaned, errors


def clean_directories(
    directories: list[str], project_root: Optional[Path] = None
) -> tuple[list[str], list[str]]:
    """Clean specified directories from project root.

    Args:
        directories: List of directory names to clean
        project_root: Project root directory (defaults to current working directory)

    Returns:
        Tuple of (cleaned_items, error_messages)
    """
    project_root = project_root or Path.cwd()
    all_cleaned: list[str] = []
    all_errors: list[str] = []

    for dir_name in directories:
        if dir_name in DIRECTORIES_TO_CLEAN:
            dir_path = project_root / dir_name
            display_name = DIRECTORIES_TO_CLEAN[dir_name]
            cleaned, errors = _safe_remove_dir(dir_path, display_name)
            all_cleaned.extend(cleaned)
            all_errors.extend(errors)

    return all_cleaned, all_errors


def clean_compiled_extensions(project_root: Optional[Path] = None) -> tuple[list[str], list[str]]:
    """Clean compiled extension files from Nuwa-managed locations.

    Removes platform-specific compiled extensions (e.g., .so, .pyd, or
    platform-specific variants like .cpython-310-x86_64-linux-gnu.so).

    Args:
        project_root: Project root directory (defaults to current working directory)

    Returns:
        Tuple of (cleaned_items, error_messages)
    """
    project_root = project_root or Path.cwd()
    cleaned = []
    errors = []

    try:
        config = parse_nuwa_config()
        lib_name = config.get("lib_name", "")
        module_name = config.get("module_name", "")
        ext = get_platform_extension()

        # Only remove the specific compiled extension that Nuwa generates
        if lib_name:
            # Check in common output locations
            for output_dir in [Path(module_name), Path("src") / module_name]:
                if output_dir.exists():
                    ext_file = output_dir / f"{lib_name}{ext}"
                    c, e = _safe_remove_file(ext_file, project_root)
                    cleaned.extend(c)
                    errors.extend(e)

    except FileNotFoundError as e:
        # pyproject.toml not found - not a Nuwa project
        errors.append(
            "Could not load pyproject.toml (not a Nuwa project?). "
            "Skipping compiled artifact cleanup."
        )
    except KeyError as e:
        # Config missing required fields
        errors.append(f"Config error: missing field {e}. Skipping artifact cleanup.")
    except (OSError, ValueError) as e:
        # I/O errors or invalid config values
        errors.append(
            f"Error cleaning artifacts: {type(e).__name__}: {e}\n"
            f"Compiled extensions may not have been cleaned. Try manually deleting compiled extension files."
        )

    return cleaned, errors


def clean_dependencies(project_root: Optional[Path] = None) -> tuple[list[str], list[str]]:
    """Clean all dependencies (.nimble/).

    Args:
        project_root: Project root directory (defaults to current working directory)

    Returns:
        Tuple of (cleaned_items, error_messages)
    """
    return clean_directories([".nimble"], project_root)


def clean_artifacts(project_root: Optional[Path] = None) -> tuple[list[str], list[str]]:
    """Clean all build artifacts (nimcache/, .nuwacache/, build/, dist/, compiled extensions).

    Args:
        project_root: Project root directory (defaults to current working directory)

    Returns:
        Tuple of (cleaned_items, error_messages)
    """
    all_cleaned = []
    all_errors = []

    # Clean directories
    artifact_dirs = ["nimcache", ".nuwacache", "build", "dist"]
    cleaned, errors = clean_directories(artifact_dirs, project_root)
    all_cleaned.extend(cleaned)
    all_errors.extend(errors)

    # Clean compiled extensions
    cleaned, errors = clean_compiled_extensions(project_root)
    all_cleaned.extend(cleaned)
    all_errors.extend(errors)

    return all_cleaned, all_errors


def clean_all(project_root: Optional[Path] = None) -> tuple[list[str], list[str]]:
    """Clean all dependencies and artifacts.

    Args:
        project_root: Project root directory (defaults to current working directory)

    Returns:
        Tuple of (cleaned_items, error_messages)
    """
    all_cleaned = []
    all_errors = []

    # Clean dependencies
    cleaned, errors = clean_dependencies(project_root)
    all_cleaned.extend(cleaned)
    all_errors.extend(errors)

    # Clean artifacts
    cleaned, errors = clean_artifacts(project_root)
    all_cleaned.extend(cleaned)
    all_errors.extend(errors)

    return all_cleaned, all_errors
