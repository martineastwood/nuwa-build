"""Wheel building utilities for Nuwa Build."""

import zipfile
from pathlib import Path
from typing import Optional

from .utils import get_wheel_tags


def write_wheel_metadata(
    zf: zipfile.ZipFile,
    name: str,
    version: str,
    tag: str = "py3-none-any"
) -> str:
    """Write wheel metadata files to the wheel archive.

    Args:
        zf: Open ZipFile object
        name: Package name
        version: Package version
        tag: Wheel tag (default: py3-none-any for pure Python/editable wheels)

    Returns:
        The dist-info directory name
    """
    dist_info = f"{name}-{version}.dist-info"

    zf.writestr(
        f"{dist_info}/WHEEL",
        f"Wheel-Version: 1.0\nGenerator: nuwa\nRoot-Is-Purelib: false\nTag: {tag}\n"
    )
    zf.writestr(
        f"{dist_info}/METADATA",
        f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n"
    )
    zf.writestr(f"{dist_info}/RECORD", "")

    return dist_info


def build_wheel_file(
    wheel_directory: str,
    name: str,
    version: str,
    files_to_add: dict[str, str],
    tag: Optional[str] = None
) -> str:
    """Build a wheel file with the given files.

    Args:
        wheel_directory: Directory to write the wheel
        name: Package name
        version: Package version
        files_to_add: Dictionary of {disk_path: archive_path}
        tag: Optional wheel tag (auto-generated if not provided)

    Returns:
        The wheel filename
    """
    wheel_name = get_wheel_tags(name, version) if tag is None else f"{name}-{version}-{tag}.whl"

    wheel_path = Path(wheel_directory) / wheel_name

    with zipfile.ZipFile(wheel_path, "w") as zf:
        # Add all files
        for disk_path, arcname in files_to_add.items():
            zf.write(disk_path, arcname=arcname)

        # Write metadata
        if tag:
            # Use specific tag
            wheel_tag = tag.replace(".whl", "")
            write_wheel_metadata(zf, name, version, wheel_tag)
        else:
            # Auto-generate tags for binary wheels
            write_wheel_metadata(zf, name, version)

    return wheel_name
