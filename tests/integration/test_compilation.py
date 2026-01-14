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

from nuwa_build.backend import build_editable, build_wheel
from nuwa_build.cli import run_new


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
