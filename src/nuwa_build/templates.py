"""Project templates for Nuwa scaffolding."""

PYPROJECT_TOML = """[build-system]
requires = ["nuwa-build"]
build-backend = "nuwa_build"

[project]
name = "{project_name}"
version = "0.1.0"
description = "A Nim extension for Python"
readme = "README.md"
requires-python = ">=3.7"
dependencies = []

[tool.nuwa]
nim-source = "nim"
module-name = "{module_name}"
lib-name = "{module_name}_lib"
entry-point = "{module_name}_lib.nim"
# Nimble dependencies (auto-installed before build)
nimble-deps = ["nimpy", "nuwa_sdk"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = "."
"""

LIB_NIM = """# Main entry point for {module_name}_lib
# This file compiles into the Python extension module
# Note: The filename determines the Python module name

import nuwa_sdk  # Provides nuwa_export for automatic type stub generation
include helpers  # Include additional modules from nim/ directory

proc greet(name: string): string {{.nuwa_export.}} =
  ## Greet someone by name
  return make_greeting(name)

proc add(a: int, b: int): int {{.nuwa_export.}} =
  ## Add two integers together
  return a + b
"""

HELPERS_NIM = """# Helper functions for {module_name}
# These functions are accessible from lib.nim

proc make_greeting(name: string): string =
  ## Create a friendly greeting
  return "Hello, " & name & "!"
"""

GITIGNORE = """# Python
__pycache__/
*.py[cod]
*.so
*.pyd
build/
dist/
*.egg-info/

# Nim
nimcache/
.nimble/
.nuwacache/
"""

INIT_PY = """\"\"\"
{module_name} - A Nim extension for Python

This package wraps the compiled Nim extension and provides Python-level functionality.

You can import Nim functions directly from the compiled extension, or wrap them
with Python code for additional processing.
\"\"\"

# Import the compiled Nim extension functions
# Note: Star imports don't work reliably with extension modules,
# so we explicitly import the functions we want to expose
from .{module_name}_lib import add, greet

__version__ = "0.1.0"

# Example: Wrap Nim functions with Python code
# def validate_dataframe(df, column_name):
#     '''Example: Extract data from pandas DataFrame and validate with Nim'''
#     import numpy as np
#     from ctypes import c_void_p
#
#     # Extract data as numpy array (zero-copy view)
#     data = df[column_name].to_numpy()
#
#     # Get pointer and pass to Nim for validation
#     from . import {module_name}_lib
#     result = {module_name}_lib.validate_array(
#         data.ctypes.data_as(c_void_p),
#         len(data)
#     )
#     return result
"""

EXAMPLE_PY = """import {module_name}

print("Testing {module_name}...")

# Test basic functionality
result = {module_name}.greet("World")
print(f"Greeting: {{result}}")
assert result == "Hello, World!", f"Expected 'Hello, World!', got '{{result}}'"

# Test addition
sum_result = {module_name}.add(5, 10)
print(f"5 + 10 = {{sum_result}}")
assert sum_result == 15, f"Expected 15, got {{sum_result}}"

print("✅ All tests passed!")
"""

TEST_PY = """\"\"\"Tests for {module_name}\"\"\"

import pytest
from {module_name} import greet, add


class TestGreet:
    \"\"\"Test the greet function.\"\"\"

    def test_greet_world(self):
        assert greet("World") == "Hello, World!"

    def test_greet_empty(self):
        assert greet("") == "Hello, !"

    def test_greet_unicode(self):
        assert greet("🐍") == "Hello, 🐍!"


class TestAdd:
    \"\"\"Test the add function.\"\"\"

    def test_add_positive(self):
        assert add(2, 3) == 5

    def test_add_negative(self):
        assert add(-1, 1) == 0
        assert add(-5, -3) == -8

    def test_add_zero(self):
        assert add(0, 0) == 0
        assert add(5, 0) == 5


def test_module_exists():
    \"\"\"Test that the module can be imported and has expected functions.\"\"\"
    import {module_name}

    assert hasattr({module_name}, 'greet')
    assert hasattr({module_name}, 'add')
    assert callable({module_name}.greet)
    assert callable({module_name}.add)
"""

README_MD = """# {project_name}

A Nim extension for Python built with [Nuwa Build](https://github.com/martineastwood/nuwa-build).

## Features

- ✅ **Zero-configuration** build system
- ✅ **Automatic type stubs** (`.pyi` files) for IDE autocomplete
- ✅ **Fast Nim compilation** with easy Python integration
- ✅ **Editable installs** for rapid development
- ✅ **GitHub Actions** workflow for automated PyPI publishing

## Installation

```bash
pip install .
```

## Development

```bash
# Compile debug build (generates .so and .pyi files)
nuwa develop

# Compile release build (optimized)
nuwa develop --release

# Run example
python example.py

# Run tests (requires pytest)
pip install pytest
pytest
```

## Type Stubs

This project automatically generates Python type stubs (`.pyi` files) during compilation. This means:

- ✨ **IDE autocomplete**: Your editor shows exact function signatures
- 🔍 **Type checking**: `mypy` and `pyright` can check your code
- 📖 **Documentation**: Docstrings appear in hover tooltips

Example type stub for `add`:
```python
def add(a: int, b: int) -> int:
    \"\"\"Add two integers together\"\"\"
    ...
```

## Project Structure

```
{project_name}/
├── .github/
│   └── workflows/
│       └── publish.yml          # PyPI/PyCI publishing workflow
├── nim/                          # Nim source files
│   ├── {module_name}_lib.nim    # Main entry point (filename = module name)
│   └── helpers.nim              # Additional modules
├── {module_name}/               # Python package
│   ├── __init__.py              # Package wrapper (can add Python code here)
│   ├── {module_name}_lib.so     # Compiled Nim extension (generated)
│   └── {module_name}_lib.pyi    # Type stubs (generated)
├── tests/                       # Test files
│   └── test_{module_name}.py    # Pytest tests
├── example.py                   # Example usage
└── pyproject.toml               # Project configuration
```

The compiled extension is named `{module_name}_lib.so` to avoid conflicts with the
Python package. Your `__init__.py` imports from it and can add Python wrappers.

## Usage

```python
import {module_name}

# Call Nim-compiled functions (with full IDE support!)
result = {module_name}.greet("World")
print(result)  # "Hello, World!"

sum_result = {module_name}.add(5, 10)
print(sum_result)  # 15
```

## Adding New Functions

1. Edit `nim/{module_name}_lib.nim`:
```nim
import nuwa_sdk

proc my_function(x: int, y: int): string {{.nuwa_export.}} =
  ## Your function documentation
  return "Result: " & $(x + y)
```

2. Recompile:
```bash
nuwa develop
```

3. Use from Python (with full autocomplete):
```python
from {module_name} import my_function

# Your IDE shows: my_function(x: int, y: int) -> str
result = my_function(5, 10)
```

## Testing

The project includes pytest tests for the Nim extension:

```bash
# Install test dependencies
pip install pytest

# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test
pytest tests/test_{module_name}.py::test_greet_world
```

## Publishing to PyPI

This project includes a GitHub Actions workflow (`.github/workflows/publish.yml`) that automatically builds and publishes wheels to PyPI when you push a version tag:

```bash
git tag v1.0.0
git push origin v1.0.0
```

The workflow uses [cibuildwheel](https://github.com/pypa/cibuildwheel) to build wheels across multiple platforms (Linux, macOS, Windows) and Python versions, then publishes them to PyPI using [Trusted Publishing](https://docs.pypi.org/trusted-publishers/).

### First-time Setup

1. **Configure Trusted Publishing** on PyPI:
   - Go to https://pypi.org/manage/account/publishing/
   - Add a new publisher with:
     - PyPI Project Name: `{project_name}`
     - Owner: Your GitHub username/organization
     - Repository name: Your repository name
     - Workflow name: `publish.yml`

2. **Push a tag** to trigger the workflow:
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```

The workflow will automatically:
- Build wheels for Linux, macOS, and Windows
- Support Python 3.9, 3.10, 3.11, 3.12, and 3.13
- Build a source distribution
- Publish everything to PyPI
"""


GITHUB_ACTIONS_PUBLISH_YML = """name: Publish to PyPI

on:
  push:
    tags:
      - "v*"
  workflow_dispatch:

jobs:
  build_wheels:
    name: Wheels on ${{ matrix.os }}
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest, macos-latest]

    env:
      PYTHONUTF8: 1
      CIBW_BUILD: "cp39-* cp310-* cp311-* cp312-* cp313-*"
      CIBW_SKIP: "pp* *-musllinux_* *i686 *-win32"

    steps:
      - uses: actions/checkout@v4

      - name: Build wheels
        uses: martineastwood/nuwa-build-action@v1
        with:
          nim-version: "2.0.0"

      - uses: actions/upload-artifact@v4
        with:
          name: cibw-wheels-${{ matrix.os }}-${{ strategy.job-index }}
          path: ./wheelhouse/*.whl

  build_sdist:
    name: Build source distribution
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Build sdist
        run: |
          pip install build
          python -m build --sdist

      - uses: actions/upload-artifact@v4
        with:
          name: cibw-sdist
          path: dist/*.tar.gz
"""

# Partial template for [tool.nuwa] section
TOOL_NUWA_SECTION = """
[tool.nuwa]
# Nim source directory
nim-source = "nim"
# Python module name (where the extension will be compiled to)
module-name = "{module_name}"
# Internal library name
lib-name = "{module_name}_lib"
# Entry point file
entry-point = "{module_name}_lib.nim"
# Nimble dependencies (auto-installed before build)
nimble-deps = ["nimpy", "nuwa_sdk"]
"""

# Partial template for build system
BUILD_SYSTEM_SECTION = """
[build-system]
requires = ["nuwa-build"]
build-backend = "nuwa_build"
"""
