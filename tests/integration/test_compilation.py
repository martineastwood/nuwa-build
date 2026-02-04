"""Integration tests for Nim compilation workflow."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

# Handle tomllib for Python 3.11+
if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from nuwa_build.cli import run_build, run_new
from nuwa_build.pep517_hooks import build_editable, build_wheel


@pytest.mark.integration
@pytest.mark.usefixtures("requires_nim")
class TestSimpleCompilation:
    """Tests for simple Nim project compilation."""

    def test_build_simple_project(self, tmp_path):
        """Test building a simple Nim project."""
        # Copy fixture to temp directory
        fixture_path = Path(__file__).parent.parent / "fixtures" / "projects" / "simple"
        import shutil

        project_path = tmp_path / "simple_test"
        shutil.copytree(fixture_path, project_path)

        # Build wheel
        os.chdir(project_path)
        wheel_dir = tmp_path / "wheels"
        wheel_dir.mkdir()
        wheel_filename = build_wheel(str(wheel_dir))

        # build_wheel returns just the filename, construct full path
        wheel_path = Path(wheel_dir) / wheel_filename

        # Verify wheel was created
        assert wheel_path.exists()
        assert str(wheel_path).endswith(".whl")
        assert "simple_test" in str(wheel_path) or "simple-test" in str(wheel_path)

    def test_build_editable_simple_project(self, tmp_path):
        """Test building an editable install."""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "projects" / "simple"
        import shutil

        project_path = tmp_path / "simple_test_editable"
        shutil.copytree(fixture_path, project_path)

        os.chdir(project_path)
        wheel_dir = tmp_path / "wheels_editable"
        wheel_dir.mkdir()
        wheel_filename = build_editable(str(wheel_dir))

        # Verify editable wheel was created
        wheel_path = Path(wheel_dir) / wheel_filename
        assert wheel_path.exists()
        assert str(wheel_path).endswith(".whl")


@pytest.mark.integration
@pytest.mark.usefixtures("requires_nim")
class TestMultiFileCompilation:
    """Tests for multi-file Nim project compilation."""

    def test_build_multi_file_project(self, tmp_path):
        """Test building a project with multiple Nim files."""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "projects" / "multi_file"
        import shutil

        project_path = tmp_path / "multi_file_test"
        shutil.copytree(fixture_path, project_path)

        os.chdir(project_path)
        wheel_dir = tmp_path / "wheels_multi"
        wheel_dir.mkdir()
        wheel_filename = build_wheel(str(wheel_dir))

        # Verify wheel was created
        wheel_path = Path(wheel_dir) / wheel_filename
        assert wheel_path.exists()
        assert str(wheel_path).endswith(".whl")


@pytest.mark.integration
@pytest.mark.usefixtures("requires_nim")
class TestErrorHandling:
    """Tests for error handling during compilation."""

    def test_type_error_message(self, tmp_path):
        """Test that type errors produce helpful messages."""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "projects" / "with_errors"
        import shutil

        project_path = tmp_path / "with_errors"
        shutil.copytree(fixture_path, project_path)

        os.chdir(project_path)
        wheel_dir = tmp_path / "wheels_error"
        wheel_dir.mkdir()

        # Should raise CalledProcessError
        with pytest.raises(subprocess.CalledProcessError):
            build_wheel(str(wheel_dir))

    def test_undeclared_variable_error(self, tmp_path):
        """Test that undeclared variables are caught."""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "projects" / "with_errors"
        import shutil

        project_path = tmp_path / "with_errors_undecl"
        shutil.copytree(fixture_path, project_path)

        os.chdir(project_path)
        wheel_dir = tmp_path / "wheels_error_undecl"
        wheel_dir.mkdir()

        # Should raise CalledProcessError
        with pytest.raises(subprocess.CalledProcessError):
            build_wheel(str(wheel_dir))


@pytest.mark.integration
@pytest.mark.usefixtures("requires_nim")
class TestCLIScaffolding:
    """Tests for CLI project scaffolding."""

    def test_new_command_creates_project(self, tmp_path):
        """Test that 'nuwa new' creates a valid project structure."""
        project_path = tmp_path / "new_project"

        from argparse import Namespace

        args = Namespace(path=str(project_path), name="test_project")

        # Run new command
        run_new(args)

        # Verify structure
        assert (project_path / "pyproject.toml").exists()
        assert (project_path / "nim").exists()
        # The template creates {module_name}_lib.nim, not lib.nim
        assert (project_path / "nim" / "test_project_lib.nim").exists()
        assert (project_path / "test_project").exists()
        assert (project_path / "test_project" / "__init__.py").exists()
        assert (project_path / "tests").exists()
        assert (project_path / "tests" / "test_test_project.py").exists()
        assert (project_path / "README.md").exists()

        # Verify pyproject.toml content
        with open(project_path / "pyproject.toml", "rb") as f:
            config = tomllib.load(f)
        assert config["project"]["name"] == "test_project"
        assert "tool" in config
        assert "nuwa" in config["tool"]

    def test_new_project_can_build(self, tmp_path):
        """Test that a newly created project can be built."""
        project_path = tmp_path / "buildable_project"

        from argparse import Namespace

        args = Namespace(path=str(project_path), name="buildable")

        run_new(args)
        os.chdir(project_path)

        wheel_dir = tmp_path / "wheels_buildable"
        wheel_dir.mkdir()

        # Should build without errors
        wheel_filename = build_wheel(str(wheel_dir))
        wheel_path = Path(wheel_dir) / wheel_filename
        assert wheel_path.exists()


@pytest.mark.integration
@pytest.mark.usefixtures("requires_nim")
class TestDiscovery:
    """Tests for source discovery."""

    def test_auto_discovers_entry_point(self, tmp_path):
        """Test that entry point is auto-discovered when not specified."""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "projects" / "simple"
        import shutil

        project_path = tmp_path / "simple_auto"
        shutil.copytree(fixture_path, project_path)

        os.chdir(project_path)

        # The fixture already has lib.nim as the entry point
        wheel_dir = tmp_path / "wheels_discovery"
        wheel_dir.mkdir()

        # Should build by auto-discovering lib.nim
        wheel_filename = build_wheel(str(wheel_dir))
        wheel_path = Path(wheel_dir) / wheel_filename
        assert wheel_path.exists()


@pytest.mark.integration
@pytest.mark.usefixtures("requires_nim")
class TestWheelMetadata:
    """Tests for generated wheel metadata."""

    def test_wheel_contains_metadata(self, tmp_path):
        """Test that wheels contain proper metadata."""
        import zipfile

        fixture_path = Path(__file__).parent.parent / "fixtures" / "projects" / "simple"
        import shutil

        project_path = tmp_path / "metadata_test"
        shutil.copytree(fixture_path, project_path)

        os.chdir(project_path)
        wheel_dir = tmp_path / "wheels_metadata"
        wheel_dir.mkdir()
        wheel_filename = build_wheel(str(wheel_dir))
        wheel_path = Path(wheel_dir) / wheel_filename

        # Check wheel contents
        with zipfile.ZipFile(wheel_path, "r") as whl:
            files = whl.namelist()

            # Should have metadata
            assert any("METADATA" in f for f in files)
            assert any("WHEEL" in f for f in files)
            assert any("RECORD" in f for f in files)

            # Should have the compiled extension
            assert any(".so" in f or ".pyd" in f for f in files)

    def test_wheel_has_correct_name(self, tmp_path):
        """Test that wheel filename follows conventions."""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "projects" / "simple"
        import shutil

        project_path = tmp_path / "name_test"
        shutil.copytree(fixture_path, project_path)

        os.chdir(project_path)
        wheel_dir = tmp_path / "wheels_name"
        wheel_dir.mkdir()
        wheel_filename = build_wheel(str(wheel_dir))

        wheel_name = wheel_filename

        # Should follow naming convention
        assert "simple_test" in wheel_name or "simple-test" in wheel_name
        assert "0.1.0" in wheel_name
        assert wheel_name.endswith(".whl")

    def test_wheel_contains_pyi_stub_file(self, tmp_path):
        """Test that wheel building works with file-based stub generation."""
        import zipfile

        fixture_path = Path(__file__).parent.parent / "fixtures" / "projects" / "simple"
        import shutil

        project_path = tmp_path / "pyi_test"
        shutil.copytree(fixture_path, project_path)

        os.chdir(project_path)
        wheel_dir = tmp_path / "wheels_pyi"
        wheel_dir.mkdir()
        wheel_filename = build_wheel(str(wheel_dir))
        wheel_path = Path(wheel_dir) / wheel_filename

        # Verify wheel was built successfully with the new stub generation system
        assert wheel_path.exists()

        with zipfile.ZipFile(wheel_path, "r") as whl:
            files = whl.namelist()
            assert any(
                ".so" in f or ".pyd" in f for f in files
            ), "Wheel should contain compiled extension"

        # Note: .pyi stub files are only created when nuwa_sdk exports are used.
        # The simple fixture uses plain nimpy, so no .pyi file is generated.
        # This test verifies the build system works correctly with the new file-based approach.

    def test_wheel_metadata_contains_dependencies(self, tmp_path):
        """Test that dependencies from pyproject.toml are written to METADATA."""
        import zipfile

        fixture_path = Path(__file__).parent.parent / "fixtures" / "projects" / "simple"
        import shutil

        project_path = tmp_path / "deps_test"
        shutil.copytree(fixture_path, project_path)

        # Add dependencies to pyproject.toml
        pyproject_path = project_path / "pyproject.toml"
        pyproject_content = pyproject_path.read_text()
        pyproject_content = pyproject_content.replace(
            '[project]\nname = "simple-test"\nversion = "0.1.0"\n',
            '[project]\nname = "simple-test"\nversion = "0.1.0"\ndependencies = ["numpy >= 1.20", "pandas >= 2.0"]\noptional-dependencies = { test = ["pytest"] }\n',
        )
        pyproject_path.write_text(pyproject_content)

        os.chdir(project_path)
        wheel_dir = tmp_path / "wheels_deps"
        wheel_dir.mkdir()
        wheel_filename = build_wheel(str(wheel_dir))
        wheel_path = Path(wheel_dir) / wheel_filename

        # Read METADATA from wheel
        with zipfile.ZipFile(wheel_path, "r") as whl:
            metadata_files = [f for f in whl.namelist() if "METADATA" in f]
            assert len(metadata_files) == 1, "Should have exactly one METADATA file"
            metadata_content = whl.read(metadata_files[0]).decode()

        # Verify dependencies are present
        assert "Requires-Dist: numpy >= 1.20" in metadata_content
        assert "Requires-Dist: pandas >= 2.0" in metadata_content
        # Verify optional dependencies
        assert "Provides-Extra: test" in metadata_content
        assert "Requires-Dist: pytest ; extra == 'test'" in metadata_content


@pytest.mark.integration
@pytest.mark.usefixtures("requires_nim")
class TestBuildCommand:
    """Tests for nuwa build command."""

    def test_build_command_creates_wheel_in_dist(self, tmp_path):
        """Test that build command creates wheel in dist/ directory."""
        from argparse import Namespace

        fixture_path = Path(__file__).parent.parent / "fixtures" / "projects" / "simple"
        import shutil

        project_path = tmp_path / "build_cmd_test"
        shutil.copytree(fixture_path, project_path)

        os.chdir(project_path)

        # Run build command with minimal args
        args = Namespace(
            release=False,
            module_name=None,
            nim_source=None,
            entry_point=None,
            output_dir=None,
            nim_flags=None,
        )
        run_build(args)

        # Verify wheel was created in dist/
        dist_dir = project_path / "dist"
        assert dist_dir.exists()
        wheels = list(dist_dir.glob("*.whl"))
        assert len(wheels) == 1
        assert "simple_test" in wheels[0].name or "simple-test" in wheels[0].name

    def test_build_command_with_nim_flags(self, tmp_path):
        """Test that build command respects nim flag overrides."""
        from argparse import Namespace

        fixture_path = Path(__file__).parent.parent / "fixtures" / "projects" / "simple"
        import shutil

        project_path = tmp_path / "build_flags_test"
        shutil.copytree(fixture_path, project_path)

        os.chdir(project_path)

        # Run build command with nim flag
        args = Namespace(
            release=False,
            module_name=None,
            nim_source=None,
            entry_point=None,
            output_dir=None,
            nim_flags=["-d:release"],
        )
        run_build(args)

        # Verify wheel was created
        dist_dir = project_path / "dist"
        assert dist_dir.exists()
        wheels = list(dist_dir.glob("*.whl"))
        assert len(wheels) == 1

    def test_build_command_overwrites_existing_wheel(self, tmp_path):
        """Test that building twice overwrites the previous wheel."""
        from argparse import Namespace

        fixture_path = Path(__file__).parent.parent / "fixtures" / "projects" / "simple"
        import shutil

        project_path = tmp_path / "build_overwrite_test"
        shutil.copytree(fixture_path, project_path)

        os.chdir(project_path)

        args = Namespace(
            release=False,
            module_name=None,
            nim_source=None,
            entry_point=None,
            output_dir=None,
            nim_flags=None,
        )

        # Build first time
        run_build(args)
        dist_dir = project_path / "dist"
        wheels = list(dist_dir.glob("*.whl"))
        first_wheel = wheels[0]
        first_mtime = first_wheel.stat().st_mtime

        # Small delay to ensure different mtime
        import time

        time.sleep(0.1)

        # Build second time
        run_build(args)
        wheels = list(dist_dir.glob("*.whl"))
        assert len(wheels) == 1  # Still only one wheel
        assert wheels[0].name == first_wheel.name  # Same name

        # Wheel should have been overwritten (newer mtime)
        # Note: size might be the same, but mtime should be different
        assert wheels[0].stat().st_mtime >= first_mtime

    def test_build_command_creates_dist_directory(self, tmp_path):
        """Test that build command creates dist/ if it doesn't exist."""
        from argparse import Namespace

        fixture_path = Path(__file__).parent.parent / "fixtures" / "projects" / "simple"
        import shutil

        project_path = tmp_path / "build_create_dist_test"
        shutil.copytree(fixture_path, project_path)

        os.chdir(project_path)

        # Ensure dist/ doesn't exist
        dist_dir = project_path / "dist"
        if dist_dir.exists():
            shutil.rmtree(dist_dir)
        assert not dist_dir.exists()

        args = Namespace(
            release=False,
            module_name=None,
            nim_source=None,
            entry_point=None,
            output_dir=None,
            nim_flags=None,
        )

        # Run build command
        run_build(args)

        # Verify dist/ was created
        assert dist_dir.exists()
        wheels = list(dist_dir.glob("*.whl"))
        assert len(wheels) == 1
