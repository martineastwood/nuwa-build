"""Unit tests for PEP 517 hooks helpers."""

import tarfile
from pathlib import Path
from zipfile import ZipFile

from wheel.wheelfile import WheelFile

from nuwa_build.pep517_hooks import (
    _add_compiled_extension,
    _add_files_from_manifest,
    _add_python_package_files,
    _build_core_metadata,
    _get_package_dir,
    _parse_manifest,
    build_sdist,
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
        _add_files_from_manifest(
            wf,
            package_dir,
            "my_pkg",
            commands,
            allow_manifest_binaries=False,
        )

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


def test_package_dir_uses_module_name_and_src_layout(tmp_path: Path, monkeypatch):
    """Distribution names must not determine the import package path."""
    config = {"module_name": "import_name", "output_location": "src"}

    assert _get_package_dir(config) == Path("src/import_name")

    package_dir = tmp_path / "src" / "import_name"
    package_dir.mkdir(parents=True)
    (package_dir / "__init__.py").write_text("VALUE = 42\n", encoding="utf-8")
    (package_dir / "data.json").write_text("{}\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    wheel_path = tmp_path / "distribution_name-1.0-py3-none-any.whl"
    with WheelFile(wheel_path, "w") as wf:
        _add_python_package_files(
            wf,
            package_dir=package_dir,
            package_arcname="import_name",
            allow_manifest_binaries=False,
        )

    with ZipFile(wheel_path) as zf:
        names = set(zf.namelist())

    assert "import_name/__init__.py" in names
    assert "import_name/data.json" in names
    assert not any(name.startswith("src/") for name in names)


def test_core_metadata_preserves_pep621_fields(tmp_path: Path):
    """Wheel metadata should preserve the static PEP 621 project metadata."""
    readme = tmp_path / "README.md"
    readme.write_text("# Example package\n", encoding="utf-8")
    pyproject = {
        "project": {
            "name": "distribution-name",
            "version": "1.2.3",
            "description": "An example native extension",
            "readme": "README.md",
            "requires-python": ">=3.10",
            "authors": [{"name": "Example Author", "email": "author@example.com"}],
            "license": {"text": "MIT"},
            "keywords": ["nim", "python"],
            "classifiers": ["Programming Language :: Python :: 3"],
            "urls": {"Repository": "https://example.com/repository"},
            "dependencies": ["numpy>=2"],
            "optional-dependencies": {"test": ["pytest>=8"]},
            "scripts": {"example-cli": "import_name.cli:main"},
        }
    }

    metadata, entry_points = _build_core_metadata(pyproject, project_dir=tmp_path)
    metadata_text = metadata.decode("utf-8")

    assert "Name: distribution-name" in metadata_text
    assert "Version: 1.2.3" in metadata_text
    assert "Summary: An example native extension" in metadata_text
    assert "Requires-Python: >=3.10" in metadata_text
    assert "Author-Email: Example Author <author@example.com>" in metadata_text
    assert "Project-URL: Repository, https://example.com/repository" in metadata_text
    assert "Requires-Dist: numpy>=2" in metadata_text
    assert "Provides-Extra: test" in metadata_text
    assert "# Example package" in metadata_text
    assert entry_points == "[console_scripts]\nexample-cli = import_name.cli:main\n"


def test_sdist_contains_pkg_info(tmp_path: Path, monkeypatch):
    """Source distributions include metadata required by package indexes."""
    project = tmp_path / "project"
    project.mkdir()
    (project / "README.md").write_text("# Example package\n", encoding="utf-8")
    (project / "pyproject.toml").write_text(
        """\
[project]
name = "example-package"
version = "1.2.3"
description = "Example package"
readme = "README.md"

[build-system]
requires = ["nuwa-build"]
build-backend = "nuwa_build"
""",
        encoding="utf-8",
    )
    package = project / "example_package"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    output = tmp_path / "dist"
    output.mkdir()
    monkeypatch.chdir(project)

    archive_name = build_sdist(str(output))

    with tarfile.open(output / archive_name, "r:gz") as archive:
        pkg_info = archive.extractfile("example-package-1.2.3/PKG-INFO")
        assert pkg_info is not None
        metadata = pkg_info.read().decode("utf-8")

    assert "Name: example-package" in metadata
    assert "Version: 1.2.3" in metadata
    assert "Summary: Example package" in metadata
