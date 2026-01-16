"""Pytest configuration and fixtures for Nuwa Build tests."""

import shutil

import pytest


def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests (slow, require Nim compiler)",
    )


@pytest.fixture
def requires_nim():
    """Skip test if Nim is not installed."""
    if not shutil.which("nim"):
        pytest.skip("Nim compiler not found in PATH")


@pytest.fixture
def requires_nimble():
    """Skip test if Nimble is not installed."""
    if not shutil.which("nimble"):
        pytest.skip("Nimble package manager not found in PATH")


def is_nim_installed():
    """Check if Nim compiler is available."""
    return shutil.which("nim") is not None


@pytest.fixture
def temp_project(tmp_path):
    """Create a temporary project directory for testing.

    Args:
        tmp_path: pytest tmp_path fixture

    Returns:
        Path to temporary project directory
    """
    project = tmp_path / "test_project"
    project.mkdir()
    return project


@pytest.fixture
def sample_nim_file(temp_project):
    """Create a sample Nim file for testing.

    Args:
        temp_project: temp_project fixture

    Returns:
        Path to the created Nim file
    """
    nim_dir = temp_project / "nim"
    nim_dir.mkdir()

    lib_file = nim_dir / "test_lib.nim"
    lib_file.write_text(
        """import nuwa_sdk

proc greet(name: string): string {.nuwa_export.} =
  return "Hello, " & name

proc add(a: int, b: int): int {.nuwa_export.} =
  return a + b
"""
    )

    helpers_file = nim_dir / "helpers.nim"
    helpers_file.write_text(
        """proc make_greeting(name: string): string =
  return "Greetings, " & name & "!"
"""
    )

    return lib_file


@pytest.fixture
def sample_pyproject(temp_project):
    """Create a sample pyproject.toml for testing.

    Args:
        temp_project: temp_project fixture

    Returns:
        Path to the created pyproject.toml
    """
    pyproject = temp_project / "pyproject.toml"
    pyproject.write_text(
        """[build-system]
requires = ["nuwa-build"]
build-backend = "nuwa_build"

[project]
name = "test-project"
version = "0.1.0"

[tool.nuwa]
nim-source = "nim"
module-name = "test_project"
lib-name = "test_project_lib"
entry-point = "test_lib.nim"
nimble-deps = []
"""
    )
    return pyproject


@pytest.fixture
def mock_config():
    """Create a mock configuration dictionary.

    Returns:
        Dictionary with default configuration
    """
    return {
        "nim_source": "nim",
        "module_name": "test_project",
        "lib_name": "test_project_lib",
        "entry_point": "test_lib.nim",
        "output_location": "auto",
        "nim_flags": [],
        "nimble_deps": [],
    }


@pytest.fixture
def working_directory():
    """Context manager for temporary directory changes during tests.

    Yields:
        Function that changes to temp directory and restores original
    """
    import os

    original = os.getcwd()

    def change_to(path):
        os.chdir(path)
        return path

    yield change_to

    os.chdir(original)
