"""PEP 517 build hooks for creating wheels and source distributions.

This module implements the PEP 517 and PEP 660 hooks for building Python wheels
and source distributions from Nim extensions.
"""

import shutil
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Optional

from wheel.wheelfile import WheelFile

from .backend import _compile_nim, _extract_metadata
from .config import load_pyproject_toml, parse_nuwa_config
from .utils import (
    copy_mingw_runtime_dlls,
    get_platform_extension,
    get_wheel_tags,
    normalize_package_name,
)


def _get_project_metadata() -> dict[str, Any]:
    """Extract project metadata from pyproject.toml.

    Returns:
        Dictionary containing dependencies and optional dependencies

    Returns empty dict if pyproject.toml not found or [project] section missing.
    """
    pyproject = load_pyproject_toml()
    if not pyproject:
        return {}

    project = pyproject.get("project", {})
    return {
        "dependencies": project.get("dependencies", []),
        "optional_dependencies": project.get("optional-dependencies", {}),
    }


def _format_metadata_entries(
    name: str, version: str, dependencies: list[str], optional_dependencies: dict[str, list[str]]
) -> str:
    """Format METADATA file content with dependencies.

    Args:
        name: Package name
        version: Package version
        dependencies: List of dependency strings (e.g., ["numpy >= 1.20"])
        optional_dependencies: Dict of extras to dependency lists

    Returns:
        Formatted METADATA content string
    """
    lines = [
        "Metadata-Version: 2.1",
        f"Name: {name}",
        f"Version: {version}",
    ]

    # Add Requires-Dist for each dependency
    for dep in dependencies:
        lines.append(f"Requires-Dist: {dep}")

    # Add optional dependencies (extras)
    for extra_name, deps in optional_dependencies.items():
        lines.append(f"Provides-Extra: {extra_name}")
        for dep in deps:
            # Mark which extra this dependency belongs to
            if ";" in dep:
                # Already has environment markers - append our extra condition
                lines.append(f"Requires-Dist: {dep} and extra == '{extra_name}'")
            else:
                # No environment markers - add extra condition
                lines.append(f"Requires-Dist: {dep} ; extra == '{extra_name}'")

    return "\n".join(lines) + "\n"


def write_wheel_metadata(wf: WheelFile, name: str, version: str, tag: str = "py3-none-any") -> str:
    """Write wheel metadata files to the wheel archive.

    Args:
        wf: Open WheelFile object
        name: Package name
        version: Package version
        tag: Wheel tag (default: py3-none-any for pure Python/editable wheels)

    Returns:
        The dist-info directory name
    """
    # Normalize package name for dist-info directory
    # Per PEP 427, dist-info directories must also use underscores
    name_normalized = normalize_package_name(name)
    dist_info = f"{name_normalized}-{version}.dist-info"

    wf.writestr(
        f"{dist_info}/WHEEL",
        f"Wheel-Version: 1.0\nGenerator: nuwa\nRoot-Is-Purelib: false\nTag: {tag}\n",
    )

    # Get project dependencies
    project_meta = _get_project_metadata()
    metadata_content = _format_metadata_entries(
        name=name,
        version=version,
        dependencies=project_meta.get("dependencies", []),
        optional_dependencies=project_meta.get("optional_dependencies", {}),
    )
    wf.writestr(f"{dist_info}/METADATA", metadata_content)

    return dist_info


def _parse_manifest(manifest_path: Path) -> dict[str, list[str]]:
    """Parse MANIFEST.in file into structured commands.

    Args:
        manifest_path: Path to MANIFEST.in file

    Returns:
        Dictionary with commands as keys and pattern lists as values
        Keys: 'include', 'exclude', 'recursive-include', 'recursive-exclude',
              'global-include', 'global-exclude'
    """
    commands: dict[str, list[str]] = {
        "include": [],
        "exclude": [],
        "recursive-include": [],
        "recursive-exclude": [],
        "global-include": [],
        "global-exclude": [],
    }

    if not manifest_path.exists():
        return commands

    with open(manifest_path) as f:
        for line in f:
            line = line.strip()
            # Skip empty lines and comments
            if not line or line.startswith("#"):
                continue

            parts = line.split()
            if len(parts) < 2:
                continue

            cmd = parts[0]
            if cmd in commands:
                commands[cmd].extend(parts[1:])

    return commands


def _add_python_package_files(wf: WheelFile, name_normalized: str) -> None:
    """Add Python package files to the wheel.

    Respects MANIFEST.in if present, otherwise includes all package data
    while excluding cache/build artifacts.

    Args:
        wf: WheelFile object to write to
        name_normalized: Normalized package name
    """
    package_dir = Path(name_normalized)
    if not package_dir.exists():
        return

    manifest_path = Path("MANIFEST.in")
    has_manifest = manifest_path.exists()

    if has_manifest:
        # Use MANIFEST.in patterns
        commands = _parse_manifest(manifest_path)
        _add_files_from_manifest(wf, package_dir, commands)
    else:
        # Default: include all package data, exclude cache/build artifacts
        _add_all_package_files(wf, package_dir)


def _add_files_from_manifest(
    wf: WheelFile, package_dir: Path, commands: dict[str, list[str]]
) -> None:
    """Add files to wheel based on MANIFEST.in commands.

    Args:
        wf: WheelFile object to write to
        package_dir: Package directory path
        commands: Parsed MANIFEST.in commands
    """
    # Track explicitly included/excluded files
    included_files: set[Path] = set()
    excluded_files: set[Path] = set()

    # Process commands in order (important for precedence)
    # Start with all .py files implicitly included (standard Python behavior)
    for py_file in package_dir.rglob("*.py"):
        included_files.add(py_file)

    # Process include patterns
    for pattern in commands["include"]:
        for file_path in package_dir.glob(pattern):
            if file_path.is_file():
                included_files.add(file_path)

    # Process recursive-include patterns (recursive-include dir patterns...)
    i = 0
    while i < len(commands["recursive-include"]):
        if i + 1 >= len(commands["recursive-include"]):
            break
        dir_pattern = commands["recursive-include"][i]
        file_patterns = commands["recursive-include"][i + 1]
        # Split multiple patterns (can be space-separated on same line)
        patterns = file_patterns.split()
        for dir_path in package_dir.glob(dir_pattern):
            if dir_path.is_dir():
                for file_path in dir_path.rglob("*"):
                    if file_path.is_file() and any(fnmatch(file_path.name, p) for p in patterns):
                        included_files.add(file_path)
        i += 2

    # Process global-include patterns
    for pattern in commands["global-include"]:
        for file_path in package_dir.rglob(pattern.split("/")[-1]):
            if file_path.is_file():
                included_files.add(file_path)

    # Process exclude patterns
    for pattern in commands["exclude"]:
        for file_path in package_dir.glob(pattern):
            if file_path.is_file():
                excluded_files.add(file_path)

    # Process recursive-exclude patterns
    i = 0
    while i < len(commands["recursive-exclude"]):
        if i + 1 >= len(commands["recursive-exclude"]):
            break
        dir_pattern = commands["recursive-exclude"][i]
        file_patterns = commands["recursive-exclude"][i + 1]
        patterns = file_patterns.split()
        for dir_path in package_dir.glob(dir_pattern):
            if dir_path.is_dir():
                for file_path in dir_path.rglob("*"):
                    if file_path.is_file() and any(fnmatch(file_path.name, p) for p in patterns):
                        excluded_files.add(file_path)
        i += 2

    # Process global-exclude patterns
    for pattern in commands["global-exclude"]:
        for file_path in package_dir.rglob("*"):
            if file_path.is_file() and fnmatch(file_path.name, pattern):
                excluded_files.add(file_path)

    # Write files that are included but not excluded
    for file_path in included_files - excluded_files:
        # Use full path for arcname (e.g., "mypackage/config.json")
        arcname = str(file_path)
        wf.write(str(file_path), arcname=arcname)


def _add_all_package_files(wf: WheelFile, package_dir: Path) -> None:
    """Add all package files to wheel, excluding cache/build artifacts.

    This is the default behavior when no MANIFEST.in is present.

    Args:
        wf: WheelFile object to write to
        package_dir: Package directory path
    """
    # Directories to always exclude
    exclude_dirs = {
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".hypothesis",
        ".stestr",
        ".coverage",
        "test_results",
        ".tox",
        ".eggs",
        "*.egg-info",
        "dist",
        "build",
        ".git",
        ".hg",
        ".svn",
        ".bzr",
        ".vscode",
        ".idea",
        "node_modules",
        "tests",
        "test",
    }

    # File patterns to always exclude
    exclude_patterns = {
        "*.pyc",
        "*.pyo",
        "*.pyd",  # Compiled extensions (added separately)
        "*.so",  # Compiled extensions (added separately)
        "*.dll",
        "*.dylib",
        "*.exe",
        "*.bat",
        ".DS_Store",
        "*.swp",
        "*.swo",
        "*~",
        "*.log",
        ".coverage",
        ".pytest_cache",
        "coverage.xml",
        "*.cover",
        ".tox.ini",
        " tox.ini",
        "MANIFEST",  # Don't include MANIFEST itself
    }

    for file_path in package_dir.rglob("*"):
        if not file_path.is_file():
            continue

        # Check if file is in an excluded directory
        if any(excluded in file_path.parts for excluded in exclude_dirs):
            continue

        # Check if file matches an excluded pattern
        if any(fnmatch(file_path.name, pattern) for pattern in exclude_patterns):
            continue

        # Exclude compiled extensions (they're added separately)
        if file_path.suffix in [".pyd", ".so", ".dll", ".dylib"]:
            continue

        # Use full path for arcname (e.g., "mypackage/config.json")
        arcname = str(file_path)
        wf.write(str(file_path), arcname=arcname)


def _add_compiled_extension(
    wf: WheelFile,
    so_file: Path,
    name_normalized: str,
    lib_name: str,
    ext: str,
) -> None:
    """Add compiled extension to the wheel.

    On Windows, also includes any DLL dependencies generated during compilation.

    Args:
        wf: WheelFile object to write to
        so_file: Path to compiled extension file (platform-specific extension)
        name_normalized: Normalized package name
        lib_name: Library name (without extension)
        ext: Platform-specific extension (e.g., .so, .pyd, .cpython-310-x86_64-linux-gnu.so)
    """
    arcname = f"{name_normalized}/{lib_name}{ext}"
    # Write with proper permissions for shared library
    wf.write(str(so_file), arcname=arcname)

    # On Windows, also bundle any DLL files generated alongside the .pyd
    # These are runtime dependencies that the .pyd needs to load
    if so_file.suffix == ".pyd":
        dlls_found = list(so_file.parent.glob("*.dll"))
        if dlls_found:
            for dll_file in dlls_found:
                dll_arcname = f"{name_normalized}/{dll_file.name}"
                wf.write(str(dll_file), arcname=dll_arcname)
                print(f"  Bundling DLL: {dll_file.name} -> {dll_arcname}")
        else:
            print(f"  No DLL files found alongside {so_file.name}")


def _add_type_stubs(
    wf: WheelFile,
    so_file: Path,
    name_normalized: str,
    lib_name: str,
) -> None:
    """Add type stub files to the wheel if they exist.

    Args:
        wf: WheelFile object to write to
        so_file: Path to compiled extension file (platform-specific extension)
        name_normalized: Normalized package name
        lib_name: Library name
    """
    # The stub file is named {lib_name}.pyi (without platform-specific tags)
    # so we need to construct the path manually instead of using with_suffix()
    pyi_file = so_file.parent / f"{lib_name}.pyi"
    if pyi_file.exists():
        arcname = f"{name_normalized}/{lib_name}.pyi"
        wf.write(str(pyi_file), arcname=arcname)


def _add_wheel_metadata(
    wf: WheelFile,
    name: str,
    version: str,
    wheel_tag: str,
    name_normalized: str,
) -> None:
    """Add WHEEL and METADATA files to the wheel.

    Args:
        wf: WheelFile object to write to
        name: Package name
        version: Package version
        wheel_tag: Wheel tag (e.g., "cp313-cp313-linux_x86_64")
        name_normalized: Normalized package name
    """
    dist_info = f"{name_normalized}-{version}.dist-info"

    wheel_content = (
        f"Wheel-Version: 1.0\nGenerator: nuwa\nRoot-Is-Purelib: false\nTag: {wheel_tag}\n"
    )
    wf.writestr(f"{dist_info}/WHEEL", wheel_content)

    # Get project dependencies
    project_meta = _get_project_metadata()
    metadata_content = _format_metadata_entries(
        name=name,
        version=version,
        dependencies=project_meta.get("dependencies", []),
        optional_dependencies=project_meta.get("optional_dependencies", {}),
    )
    wf.writestr(f"{dist_info}/METADATA", metadata_content)


def _cleanup_build_artifacts(so_file: Path, lib_name: str) -> None:
    """Clean up temporary build artifacts.

    Args:
        so_file: Path to compiled extension
        lib_name: Library name (for finding stub file)
    """
    if so_file.exists():
        so_file.unlink()
    # The stub file is named {lib_name}.pyi (without platform-specific tags)
    pyi_file = so_file.parent / f"{lib_name}.pyi"
    if pyi_file.exists():
        pyi_file.unlink()

    # On Windows, also clean up any DLL files generated during compilation
    # (these have already been bundled into the wheel at this point)
    if so_file.suffix == ".pyd":
        for dll_file in so_file.parent.glob("*.dll"):
            if dll_file.exists():
                dll_file.unlink()


# --- PEP 517 Hooks ---


def build_wheel(
    wheel_directory: str,
    config_settings: Optional[dict] = None,
    metadata_directory: Optional[str] = None,  # noqa: ARG001
) -> str:
    """Build a standard wheel with valid RECORD and permissions.

    Uses wheel.WheelFile which automatically handles:
    - RECORD file generation with proper hashes
    - PEP 427 compliance
    - File permissions and metadata

    Args:
        wheel_directory: Directory to write the wheel
        config_settings: Optional build settings (supports config_overrides)
        metadata_directory: Optional metadata directory

    Returns:
        The wheel filename
    """

    # Convert config_settings to config_overrides format if provided
    config_overrides = None
    if config_settings and "config_overrides" in config_settings:
        config_overrides = config_settings["config_overrides"]

    so_file = _compile_nim(build_type="release", inplace=False, config_overrides=config_overrides)

    # On Windows, copy MinGW runtime DLLs to the same directory as the .pyd
    # These DLLs will be bundled with the wheel
    if so_file.suffix == ".pyd":
        copy_mingw_runtime_dlls(so_file.parent)

    # Extract metadata
    name, version = _extract_metadata()
    config = parse_nuwa_config()
    lib_name = config["lib_name"]
    ext = get_platform_extension()

    # Normalize package name
    name_normalized = normalize_package_name(name)

    # Get wheel name and extracted tag
    wheel_name = get_wheel_tags(name, version)
    wheel_tag = wheel_name[:-4].split("-", 2)[2]
    wheel_path = Path(wheel_directory) / wheel_name

    # Use WheelFile for automatic RECORD generation
    with WheelFile(wheel_path, "w") as wf:
        # 1. Add Python package files
        _add_python_package_files(wf, name_normalized)

        # 2. Add compiled extension
        _add_compiled_extension(wf, so_file, name_normalized, lib_name, ext)

        # 3. Add type stubs
        _add_type_stubs(wf, so_file, name_normalized, lib_name)

        # 4. Add metadata
        _add_wheel_metadata(wf, name, version, wheel_tag, name_normalized)

    # Cleanup
    _cleanup_build_artifacts(so_file, lib_name)

    return wheel_path.name


def build_sdist(
    sdist_directory: str,
    config_settings: Optional[dict] = None,  # noqa: ARG001
) -> str:
    """Build a source distribution.

    Args:
        sdist_directory: Directory to write the source distribution
        config_settings: Optional build settings

    Returns:
        The source distribution filename
    """

    # Extract metadata
    name, version = _extract_metadata()

    # Create source distribution archive
    base_name = f"{name}-{version}"
    archive_name = f"{base_name}.tar.gz"
    shutil.make_archive(str(Path(sdist_directory) / base_name), "gztar", root_dir=".")

    return archive_name


# --- PEP 660 Hooks (Editable Installs) ---


def build_editable(
    wheel_directory: str,
    config_settings: Optional[dict] = None,  # noqa: ARG001
    metadata_directory: Optional[str] = None,  # noqa: ARG001
) -> str:
    """Build an editable wheel (pip install -e .).

    Args:
        wheel_directory: Directory to write the wheel
        config_settings: Optional build settings
        metadata_directory: Optional metadata directory

    Returns:
        The wheel filename
    """

    # Compile in-place
    _compile_nim(build_type="debug", inplace=True)

    # Extract metadata
    name, version = _extract_metadata()

    # Normalize package name
    name_normalized = normalize_package_name(name)

    # Create editable wheel
    wheel_name = f"{name_normalized}-{version}-py3-none-any.whl"
    wheel_path = Path(wheel_directory) / wheel_name

    with WheelFile(wheel_path, "w") as wf:
        # Point python to the project root (flat layout)
        wf.writestr(f"{name}.pth", str(Path.cwd()))

        # Write metadata
        write_wheel_metadata(wf, name, version, tag="py3-none-any")

    return wheel_name


# Boilerplate required hooks
def get_requires_for_build_wheel(
    config_settings: Optional[dict] = None,  # noqa: ARG001
) -> list:
    """Return build requirements for wheels."""
    return []


def get_requires_for_build_sdist(
    config_settings: Optional[dict] = None,  # noqa: ARG001
) -> list:
    """Return build requirements for source distributions."""
    return []


def get_requires_for_build_editable(
    config_settings: Optional[dict] = None,  # noqa: ARG001
) -> list:
    """Return build requirements for editable installs."""
    return []
