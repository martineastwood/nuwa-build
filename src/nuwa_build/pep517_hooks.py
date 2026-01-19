"""PEP 517 build hooks for creating wheels and source distributions.

This module implements the PEP 517 and PEP 660 hooks for building Python wheels
and source distributions from Nim extensions.
"""

import logging
import shutil
from pathlib import Path
from typing import Optional

from wheel.wheelfile import WheelFile

from .config import parse_nuwa_config
from .utils import get_platform_extension, get_wheel_tags, normalize_package_name
from .wheel_utils import write_wheel_metadata

logger = logging.getLogger("nuwa")


# Import compilation function from backend (avoid circular dependency)
# This will be imported at the bottom of the file to avoid circular imports


def _add_python_package_files(wf: WheelFile, name_normalized: str) -> None:
    """Add Python package files to the wheel.

    Args:
        wf: WheelFile object to write to
        name_normalized: Normalized package name
    """
    package_dir = Path(name_normalized)
    if package_dir.exists():
        for py_file in package_dir.rglob("*.py"):
            arcname = str(py_file)
            wf.write(str(py_file), arcname=arcname)


def _add_compiled_extension(
    wf: WheelFile,
    so_file: Path,
    name_normalized: str,
    lib_name: str,
    ext: str,
) -> None:
    """Add compiled extension to the wheel.

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
    pyi_file = so_file.with_suffix(".pyi")
    if pyi_file.exists():
        arcname = f"{name_normalized}/{lib_name}.pyi"
        wf.write(str(pyi_file), arcname=arcname)
        logger.info(f"Including type stubs: {lib_name}.pyi")


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

    metadata_content = f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n"
    wf.writestr(f"{dist_info}/METADATA", metadata_content)


def _cleanup_build_artifacts(so_file: Path) -> None:
    """Clean up temporary build artifacts.

    Args:
        so_file: Path to compiled extension
    """
    if so_file.exists():
        so_file.unlink()
    pyi_file = so_file.with_suffix(".pyi")
    if pyi_file.exists():
        pyi_file.unlink()


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
    # Import here to avoid circular dependency
    from .backend import _compile_nim, _extract_metadata

    # Convert config_settings to config_overrides format if provided
    config_overrides = None
    if config_settings and "config_overrides" in config_settings:
        config_overrides = config_settings["config_overrides"]

    so_file = _compile_nim(build_type="release", inplace=False, config_overrides=config_overrides)

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
    _cleanup_build_artifacts(so_file)

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
    # Import here to avoid circular dependency
    from .backend import _extract_metadata

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
    # Import here to avoid circular dependency
    from .backend import _compile_nim, _extract_metadata

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
