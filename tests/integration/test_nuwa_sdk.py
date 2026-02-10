"""Integration tests for nuwa-sdk features."""

import os
import shutil
import sys
import zipfile
from pathlib import Path

import pytest

from nuwa_build.pep517_hooks import build_wheel


@pytest.mark.integration
@pytest.mark.usefixtures("requires_nim")
class TestNuwaSdkBasicExports:
    """Tests for basic nuwa_export functionality."""

    def test_exported_functions_callable(self, tmp_path):
        """Test that exported functions are callable from Python."""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "projects" / "nuwa_sdk"
        project_path = tmp_path / "nuwa_sdk_basic"
        shutil.copytree(fixture_path, project_path)

        os.chdir(project_path)
        wheel_dir = tmp_path / "wheels_basic"
        wheel_dir.mkdir()
        wheel_filename = build_wheel(str(wheel_dir))
        wheel_path = Path(wheel_dir) / wheel_filename

        # Install and import
        with zipfile.ZipFile(wheel_path, "r") as whl:
            # Extract to a temporary location for import
            extract_dir = tmp_path / "extracted_basic"
            whl.extractall(extract_dir)
            sys.path.insert(0, str(extract_dir))

        try:
            import nuwa_sdk_test

            # Test basic functions
            assert nuwa_sdk_test.addInts(3, 5) == 8
            assert abs(nuwa_sdk_test.addFloats(2.5, 3.7) - 6.2) < 1e-10
            assert nuwa_sdk_test.greet("World") == "Hello, World!"
        finally:
            sys.path.remove(str(extract_dir))
            # Clean up module cache to prevent test interference
            sys.modules.pop("nuwa_sdk_test", None)
            sys.modules.pop("nuwa_sdk_test.nuwa_sdk_test_lib", None)

    def test_stub_file_generation(self, tmp_path):
        """Test that .pyi stub files are generated for exported functions."""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "projects" / "nuwa_sdk"
        project_path = tmp_path / "nuwa_sdk_stubs"
        shutil.copytree(fixture_path, project_path)

        os.chdir(project_path)
        wheel_dir = tmp_path / "wheels_stubs"
        wheel_dir.mkdir()
        wheel_filename = build_wheel(str(wheel_dir))
        wheel_path = Path(wheel_dir) / wheel_filename

        # Check that .pyi file exists in wheel
        with zipfile.ZipFile(wheel_path, "r") as whl:
            files = whl.namelist()
            pyi_files = [f for f in files if f.endswith(".pyi")]

            # Should have at least one .pyi file
            assert len(pyi_files) > 0, "No .pyi stub files found in wheel"

            # Extract and verify stub content
            for pyi_file in pyi_files:
                stub_content = whl.read(pyi_file).decode()

                # Check for function signatures
                assert "def addInts" in stub_content
                assert "def greet" in stub_content

                # Check for docstrings
                assert "Add two integers" in stub_content or "Return a greeting" in stub_content


@pytest.mark.integration
@pytest.mark.usefixtures("requires_nim")
class TestNuwaSdkSequences:
    """Tests for sequence type handling."""

    def test_sum_int_sequence(self, tmp_path):
        """Test summing a sequence of integers."""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "projects" / "nuwa_sdk"
        project_path = tmp_path / "nuwa_sdk_sequences"
        shutil.copytree(fixture_path, project_path)

        os.chdir(project_path)
        wheel_dir = tmp_path / "wheels_sequences"
        wheel_dir.mkdir()
        wheel_filename = build_wheel(str(wheel_dir))
        wheel_path = Path(wheel_dir) / wheel_filename

        # Install and import
        with zipfile.ZipFile(wheel_path, "r") as whl:
            extract_dir = tmp_path / "extracted_sequences"
            whl.extractall(extract_dir)
            sys.path.insert(0, str(extract_dir))

        try:
            import nuwa_sdk_test

            # Test sequence sum
            result = nuwa_sdk_test.sumIntSequence([1, 2, 3, 4, 5])
            assert result == 15

            # Test with larger sequence
            result = nuwa_sdk_test.sumIntSequence(list(range(100)))
            assert result == sum(range(100))
        finally:
            sys.path.remove(str(extract_dir))
            # Clean up module cache to prevent test interference
            sys.modules.pop("nuwa_sdk_test", None)
            sys.modules.pop("nuwa_sdk_test.nuwa_sdk_test_lib", None)

    def test_multiply_sequence(self, tmp_path):
        """Test multiplying sequence elements by scalar."""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "projects" / "nuwa_sdk"
        project_path = tmp_path / "nuwa_sdk_multiply"
        shutil.copytree(fixture_path, project_path)

        os.chdir(project_path)
        wheel_dir = tmp_path / "wheels_multiply"
        wheel_dir.mkdir()
        wheel_filename = build_wheel(str(wheel_dir))
        wheel_path = Path(wheel_dir) / wheel_filename

        with zipfile.ZipFile(wheel_path, "r") as whl:
            extract_dir = tmp_path / "extracted_multiply"
            whl.extractall(extract_dir)
            sys.path.insert(0, str(extract_dir))

        try:
            import nuwa_sdk_test

            result = nuwa_sdk_test.multiplySequence([1.0, 2.0, 3.0, 4.0], 2.5)
            assert len(result) == 4
            assert abs(result[0] - 2.5) < 1e-10
            assert abs(result[1] - 5.0) < 1e-10
            assert abs(result[2] - 7.5) < 1e-10
            assert abs(result[3] - 10.0) < 1e-10
        finally:
            sys.path.remove(str(extract_dir))
            # Clean up module cache to prevent test interference
            sys.modules.pop("nuwa_sdk_test", None)
            sys.modules.pop("nuwa_sdk_test.nuwa_sdk_test_lib", None)


@pytest.mark.integration
@pytest.mark.usefixtures("requires_nim")
class TestNuwaSdkGILRelease:
    """Tests for GIL release functionality."""

    def test_sum_with_nogil(self, tmp_path):
        """Test that withNogil releases GIL correctly."""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "projects" / "nuwa_sdk"
        project_path = tmp_path / "nuwa_sdk_gil"
        shutil.copytree(fixture_path, project_path)

        os.chdir(project_path)
        wheel_dir = tmp_path / "wheels_gil"
        wheel_dir.mkdir()
        wheel_filename = build_wheel(str(wheel_dir))
        wheel_path = Path(wheel_dir) / wheel_filename

        with zipfile.ZipFile(wheel_path, "r") as whl:
            extract_dir = tmp_path / "extracted_gil"
            whl.extractall(extract_dir)
            sys.path.insert(0, str(extract_dir))

        try:
            import nuwa_sdk_test

            # Test basic functionality
            result = nuwa_sdk_test.sumWithNogil(10)
            assert result == sum(range(10))

            # Test with larger value
            result = nuwa_sdk_test.sumWithNogil(100)
            assert result == sum(range(100))

            # Compare with Python sum
            for n in [5, 10, 50]:
                result = nuwa_sdk_test.sumWithNogil(n)
                expected = sum(range(n))
                assert result == expected
        finally:
            sys.path.remove(str(extract_dir))
            # Clean up module cache to prevent test interference
            sys.modules.pop("nuwa_sdk_test", None)
            sys.modules.pop("nuwa_sdk_test.nuwa_sdk_test_lib", None)


@pytest.mark.integration
@pytest.mark.usefixtures("requires_nim")
class TestNuwaSdkTypeConversions:
    """Tests for type conversions between Python and Nim."""

    def test_mixed_types(self, tmp_path):
        """Test handling various Python types."""
        fixture_path = Path(__file__).parent.parent / "fixtures" / "projects" / "nuwa_sdk"
        project_path = tmp_path / "nuwa_sdk_mixed"
        shutil.copytree(fixture_path, project_path)

        os.chdir(project_path)
        wheel_dir = tmp_path / "wheels_mixed"
        wheel_dir.mkdir()
        wheel_filename = build_wheel(str(wheel_dir))
        wheel_path = Path(wheel_dir) / wheel_filename

        with zipfile.ZipFile(wheel_path, "r") as whl:
            extract_dir = tmp_path / "extracted_mixed"
            whl.extractall(extract_dir)
            sys.path.insert(0, str(extract_dir))

        try:
            import nuwa_sdk_test

            result = nuwa_sdk_test.processMixedTypes(5, 2.5, "test", True)
            # Nim tuples are converted to Python tuples (named fields are lost)
            assert result[0] == 10  # int_val
            assert abs(result[1] - 5.0) < 1e-10  # float_val
            assert result[2] == "test processed"  # str_val
            assert result[3] is False  # bool_val
        finally:
            sys.path.remove(str(extract_dir))
            # Clean up module cache to prevent test interference
            sys.modules.pop("nuwa_sdk_test", None)
            sys.modules.pop("nuwa_sdk_test.nuwa_sdk_test_lib", None)
