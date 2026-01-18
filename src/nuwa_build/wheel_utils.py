"""Wheel building utilities for Nuwa Build."""

from pathlib import Path
from typing import Dict, Optional

from wheel.wheelfile import WheelFile

from .utils import get_wheel_tags


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
    name_normalized = name.replace("-", "_")
    dist_info = f"{name_normalized}-{version}.dist-info"

    wf.writestr(
        f"{dist_info}/WHEEL",
        f"Wheel-Version: 1.0\nGenerator: nuwa\nRoot-Is-Purelib: false\nTag: {tag}\n",
    )
    wf.writestr(
        f"{dist_info}/METADATA",
        f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n",
    )

    return dist_info


def build_wheel_file(
    wheel_directory: str,
    name: str,
    version: str,
    files_to_add: Dict[str, str],
    tag: Optional[str] = None,
) -> str:
    """Build a wheel file with the given files.

    Uses WheelFile which automatically handles RECORD generation and hash calculation.

    Args:
        wheel_directory: Directory to write the wheel
        name: Package name
        version: Package version
        files_to_add: Dictionary of {disk_path: archive_path}
        tag: Optional wheel tag (auto-generated if not provided)

    Returns:
        The wheel filename
    """
    # Normalize package name: replace hyphens with underscores
    # Per PEP 427, wheel filenames must use underscores even if the package name uses hyphens
    name_normalized = name.replace("-", "_")

    wheel_name = (
        get_wheel_tags(name, version) if tag is None else f"{name_normalized}-{version}-{tag}.whl"
    )

    wheel_path = Path(wheel_directory) / wheel_name

    with WheelFile(wheel_path, "w") as wf:
        # Add all files
        for disk_path, arcname in files_to_add.items():
            wf.write(disk_path, arcname=arcname)

        # Write metadata
        if tag:
            # Use specific tag
            wheel_tag = tag.replace(".whl", "")
            write_wheel_metadata(wf, name, version, wheel_tag)
        else:
            # Auto-generate tags for binary wheels
            write_wheel_metadata(wf, name, version)

    return wheel_name
