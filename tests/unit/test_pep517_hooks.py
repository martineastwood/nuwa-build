"""Unit tests for PEP 517 hooks helpers."""

from pathlib import Path
from zipfile import ZipFile

from wheel.wheelfile import WheelFile

from nuwa_build.pep517_hooks import (
    _add_compiled_extension,
    _add_files_from_manifest,
    _parse_manifest,
)


def test_manifest_recursive_patterns(tmp_path: Path):
    """Test recursive-include/exclude with multiple patterns."""
    package_dir = tmp_path / "my_pkg"
    data_dir = package_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # Files to include/exclude
    (package_dir / "__init__.py").write_text("# pkg", encoding="utf-8")
    (data_dir / "keep.txt").write_text("ok", encoding="utf-8")
    (data_dir / "keep.json").write_text("ok", encoding="utf-8")
    (data_dir / "drop.log").write_text("nope", encoding="utf-8")
    (data_dir / "drop.tmp").write_text("nope", encoding="utf-8")

    manifest = tmp_path / "MANIFEST.in"
    manifest.write_text(
        "\n".join(
            [
                "recursive-include data *.txt *.json",
                "recursive-exclude data *.log *.tmp",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    commands = _parse_manifest(manifest)

    wheel_path = tmp_path / "my_pkg-0.0.0-py3-none-any.whl"
    with WheelFile(wheel_path, "w") as wf:
        _add_files_from_manifest(wf, package_dir, commands, allow_manifest_binaries=False)

    with ZipFile(wheel_path) as zf:
        names = set(zf.namelist())

    assert any(name.endswith("my_pkg/data/keep.txt") for name in names)
    assert any(name.endswith("my_pkg/data/keep.json") for name in names)
    assert not any(name.endswith("my_pkg/data/drop.log") for name in names)
    assert not any(name.endswith("my_pkg/data/drop.tmp") for name in names)


def test_bundle_adjacent_dlls(tmp_path: Path):
    """Test bundling adjacent DLLs can be toggled."""
    pkg_dir = tmp_path / "my_pkg"
    pkg_dir.mkdir(parents=True, exist_ok=True)

    so_file = pkg_dir / "my_pkg_lib.pyd"
    dll_file = pkg_dir / "helper.dll"
    so_file.write_text("pyd", encoding="utf-8")
    dll_file.write_text("dll", encoding="utf-8")

    wheel_path = tmp_path / "my_pkg-0.0.0-py3-none-any.whl"

    with WheelFile(wheel_path, "w") as wf:
        _add_compiled_extension(
            wf,
            so_file,
            name_normalized="my_pkg",
            lib_name="my_pkg_lib",
            ext=".pyd",
            bundle_adjacent_dlls=False,
        )

    with ZipFile(wheel_path) as zf:
        names = set(zf.namelist())

    assert any(name.endswith("my_pkg/my_pkg_lib.pyd") for name in names)
    assert not any(name.endswith("my_pkg/helper.dll") for name in names)

    wheel_path = tmp_path / "my_pkg-0.0.1-py3-none-any.whl"
    with WheelFile(wheel_path, "w") as wf:
        _add_compiled_extension(
            wf,
            so_file,
            name_normalized="my_pkg",
            lib_name="my_pkg_lib",
            ext=".pyd",
            bundle_adjacent_dlls=True,
        )

    with ZipFile(wheel_path) as zf:
        names = set(zf.namelist())

    assert any(name.endswith("my_pkg/my_pkg_lib.pyd") for name in names)
    assert any(name.endswith("my_pkg/helper.dll") for name in names)
