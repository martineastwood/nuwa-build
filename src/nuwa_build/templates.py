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
nimble-deps = ["nimpy"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = "."
"""

LIB_NIM = """# Main entry point for {module_name}_lib
# This file compiles into the Python extension module
# Note: The filename determines the Python module name

import nimpy
include helpers  # Include additional modules from nim/ directory

proc greet(name: string): string {{.exportpy.}} =
  ## Greet someone by name
  return make_greeting(name)

proc add(a: int, b: int): int {{.exportpy.}} =
  ## Add two integers together
  return a + b
"""

HELPERS_NIM = """# Helper functions for {module_name}
# These functions are accessible from lib.nim

proc make_greeting(name: string): string =
  ## Create a friendly greeting
  return "Hello, " & name & "!"
"""

INIT_PY = """\"\"\"
{module_name} - A Nim extension for Python

This package provides Python bindings to Nim-compiled functions.
\"\"\"

__version__ = "0.1.0"
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

## Installation

```bash
pip install .
```

## Development

```bash
# Compile debug build
nuwa develop

# Compile release build
nuwa develop --release

# Run example
python example.py

# Run tests (requires pytest)
pip install pytest
pytest
```

## Project Structure

```
{project_name}/
├── nim/                          # Nim source files
│   ├── {module_name}_lib.nim    # Main entry point (filename = module name)
│   └── helpers.nim              # Additional modules
├── {module_name}/               # Python package
│   ├── __init__.py              # Package wrapper (can add Python code here)
│   └── {module_name}_lib.so     # Compiled Nim extension (generated)
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

# Call Nim-compiled functions
result = {module_name}.greet("World")
print(result)  # "Hello, World!"

sum_result = {module_name}.add(5, 10)
print(sum_result)  # 15
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
"""
