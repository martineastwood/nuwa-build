"""Source discovery for Nim projects."""

from pathlib import Path
from typing import List, Tuple


def discover_nim_sources(config: dict) -> Tuple[Path, Path]:
    """Discover Nim entry point and source directory.

    Args:
        config: Configuration dictionary with nim_source and entry_point

    Returns:
        Tuple of (nim_source_dir, entry_point_file)

    Raises:
        FileNotFoundError: If Nim directory or entry point not found
        ValueError: If ambiguous entry point detection
    """
    nim_dir = Path(config["nim_source"])

    if not nim_dir.exists():
        raise FileNotFoundError(
            f"Nim source directory not found: {nim_dir}\n"
            f"Ensure your project has a '{config['nim_source']}' directory with Nim source files."
        )

    if not nim_dir.is_dir():
        raise ValueError(f"Nim source path is not a directory: {nim_dir}")

    # Find entry point
    entry_point_name = config["entry_point"]
    entry_point = nim_dir / entry_point_name

    if entry_point.exists():
        return nim_dir, entry_point

    # Fallback: try to discover entry point
    return discover_entry_point_fallback(nim_dir, config["module_name"])


def discover_entry_point_fallback(nim_dir: Path, module_name: str) -> Tuple[Path, Path]:
    """Fallback entry point discovery when explicit file not found.

    Strategy:
    1. Look for {module_name}_lib.nim
    2. Look for lib.nim
    3. Use first .nim file if only one exists
    4. Error if ambiguous

    Args:
        nim_dir: Path to Nim source directory
        module_name: Python module name

    Returns:
        Tuple of (nim_dir, entry_point_file)

    Raises:
        FileNotFoundError: If no .nim files found
        ValueError: If ambiguous (multiple files, no clear entry point)
    """
    nim_files = list(nim_dir.glob("*.nim"))

    if not nim_files:
        raise FileNotFoundError(
            f"No .nim files found in {nim_dir}\n"
            f"Ensure your project has Nim source files in the {nim_dir} directory."
        )

    # Strategy 1: Match {module_name}_lib.nim
    lib_file = nim_dir / f"{module_name}_lib.nim"
    if lib_file in nim_files:
        return nim_dir, lib_file

    # Strategy 2: Look for lib.nim (common convention)
    lib_file = nim_dir / "lib.nim"
    if lib_file in nim_files:
        return nim_dir, lib_file

    # Strategy 3: Single file
    if len(nim_files) == 1:
        return nim_dir, nim_files[0]

    # Strategy 4: Error with helpful message
    raise ValueError(
        f"Multiple .nim files found in {nim_dir}. "
        f"Please specify entry point in pyproject.toml:\n"
        f"  [tool.nuwa]\n"
        f'  entry-point = "<filename>.nim"\n\n'
        f"Found files: {[f.name for f in nim_files]}"
    )


def validate_nim_project(nim_dir: Path, entry_point: Path) -> List[Path]:
    """Validate Nim project structure and return all .nim files.

    Args:
        nim_dir: Path to Nim source directory
        entry_point: Path to entry point file

    Returns:
        List of all .nim files in the project

    Raises:
        FileNotFoundError: If entry point doesn't exist
    """
    if not entry_point.exists():
        raise FileNotFoundError(
            f"Entry point not found: {entry_point}\nEnsure the file exists: {entry_point}"
        )

    # Find all Nim files for dependency checking
    nim_files = list(nim_dir.glob("*.nim"))

    return nim_files
