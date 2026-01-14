# Nuwa Build

Build Python extensions with Nim using zero-configuration tooling.

**Repository:** https://github.com/martineastwood/nuwa-build

## Features

- **Zero Configuration**: Works out of the box with sensible defaults
- **Multi-file Projects**: Compile multiple Nim files into a single Python extension
- **Flexible Configuration**: Configure via `pyproject.toml` or CLI arguments
- **PEP 517/660 Compatible**: Build wheels and source distributions
- **Editable Installs**: `pip install -e .` support for development
- **Watch Mode**: Auto-recompile on file changes with `nuwa watch`
- **Auto Dependencies**: Automatically install Nimble packages before build
- **Testing Support**: Includes pytest tests in project template
- **Validation**: Validates configuration and provides helpful error messages
- **Proper Platform Tags**: Generates correct wheel tags for your platform

## Installation

```bash
# Install Nuwa
pip install nuwa-build

# Install nimpy (Nim-Python bridge)
nimble install nimpy
```

**Requirements**:
- Python 3.7+
- Nim compiler (must be installed and available in your PATH)
- nimpy library (install via `nimble install nimpy`)

## Quick Start

### 1. Create a New Project

```bash
nuwa new my_project
cd my_project
```

This creates:
```
my_project/
├── pyproject.toml           # Python project config
├── nim/                     # Nim source files
│   ├── my_project_lib.nim  # Main entry point (filename = module name)
│   └── helpers.nim          # Additional modules
├── my_project/              # Python package
│   ├── __init__.py          # Package wrapper
│   └── my_project_lib.so    # Compiled extension (generated)
├── tests/                   # Test files
│   └── test_my_project.py   # Pytest tests
├── example.py               # Example/test file
└── README.md
```

### 2. Build and Test

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

**Note**: No `pip install -e .` needed! With flat layout, you can run `python example.py` and `pytest` directly after compiling.

### 3. Watch Mode

For development, use watch mode to automatically recompile when you change Nim files:

```bash
# Watch for changes and auto-recompile
nuwa watch

# Watch with tests after each compile
nuwa watch --run-tests

# Watch in release mode
nuwa watch --release
```

### 4. Install and Distribute

```bash
# Build a wheel
pip install . --no-build-isolation

# Build source distribution
python -m build
```

## Project Structure

Nuwa uses a simple flat layout for easy development:

```
project/
├── pyproject.toml              # Configuration
├── nim/                        # Nim source files
│   ├── my_package_lib.nim     # Main entry point (determines module name)
│   └── helpers.nim             # Additional modules
├── my_package/                 # Python package
│   ├── __init__.py             # Package wrapper (can add Python code)
│   └── my_package_lib.so       # Compiled Nim extension (generated)
└── tests/
    └── test_my_package.py      # Pytest tests
```

The compiled extension is named `{module_name}_lib.so` to avoid conflicts with the Python package. Your `__init__.py` imports from it and can add Python wrappers.

## Configuration

### pyproject.toml

Configure your project in the `[tool.nuwa]` section:

```toml
[build-system]
requires = ["nuwa-build"]
build-backend = "nuwa_build"

[project]
name = "my-package"
version = "0.1.0"

[tool.nuwa]
# Nim source directory (default: "nim")
nim-source = "nim"

# Python module name (default: derived from project name)
module-name = "my_package"

# Internal library name (default: "{module_name}_lib")
lib-name = "my_package_lib"

# Entry point file (default: "{lib_name}.nim")
entry-point = "my_package_lib.nim"

# Output location: "auto", "src", or explicit path
output-location = "auto"

# Additional Nim compiler flags (optional)
nim-flags = []

# Nimble dependencies (auto-installed before build)
nimble-deps = ["nimpy", "cligen >= 1.0.0"]
```

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `nim-source` | string | `"nim"` | Directory containing Nim source files |
| `module-name` | string | Derived from project name | Python package name |
| `lib-name` | string | `{module_name}_lib` | Internal compiled extension name |
| `entry-point` | string | `{lib_name}.nim` | Main entry point file (relative to `nim-source`) |
| `output-location` | string | `"auto"` | Where to place compiled extension (`"auto"`, `"src"`, or path) |
| `nim-flags` | list | `[]` | Additional compiler flags |
| `nimble-deps` | list | `[]` | Nimble packages to auto-install before build |

**Note**: The entry point filename determines the Python module name of the compiled extension. If your entry point is `my_package_lib.nim`, the module will be importable as `my_package_lib`.

## CLI Commands

### `nuwa new <path>`

Create a new project scaffold:

```bash
nuwa new my_project
nuwa new my_project --name custom-name
```

### `nuwa develop`

Compile the project in-place:

```bash
# Debug build
nuwa develop

# Release build
nuwa develop --release

# Override configuration
nuwa develop --module-name my_module
nuwa develop --nim-source my_nim_dir
nuwa develop --entry-point main.nim
nuwa develop --output-dir build/
nuwa develop --nim-flag="-d:danger" --nim-flag="--opt:size"
```

**Note**: After running `nuwa develop`, the compiled extension will be in `{module_name}/`. You can then run `python example.py` or `pytest` directly without any installation step.

### `nuwa watch`

Watch for file changes and automatically recompile:

```bash
# Watch for changes and auto-recompile
nuwa watch

# Watch with tests after each compile
nuwa watch --run-tests

# Watch in release mode
nuwa watch --release

# Override configuration
nuwa watch --module-name my_module
nuwa watch --nim-source my_nim_dir
```

## Entry Point Discovery

If `entry-point` is not specified, Nuwa will automatically discover the main entry point using this priority:

1. Explicit `[tool.nuwa] entry-point` configuration
2. `{module_name}_lib.nim` (matches the lib-name)
3. `lib.nim` (fallback convention)
4. First (and only) `.nim` file if only one exists
5. Error if multiple files found and no clear entry point

## Mixing Python and Nim

Your `__init__.py` can import from the compiled Nim extension and add Python wrappers:

```python
# In my_package/__init__.py
from .my_package_lib import *

__version__ = "0.1.0"

# Example: Wrap Nim functions with Python code
def validate_dataframe(df, column_name):
    """Extract pandas data and pass to Nim for zero-copy validation"""
    import numpy as np
    from ctypes import c_void_p

    # Extract data as numpy array (zero-copy view)
    data = df[column_name].to_numpy()

    # Get pointer and pass to Nim for validation
    result = validate_array_raw(
        data.ctypes.data_as(c_void_p),
        len(data)
    )
    return result
```

This allows you to:
- Use Python to extract/prepare data (e.g., from pandas DataFrames)
- Pass pointers/arrays to Nim for zero-copy processing
- Return results back to Python for formatting

## Multi-File Projects

Nim's module system handles dependencies automatically. Use `include` to add code from other Nim files:

**nim/my_package_lib.nim:**
```nim
import nimpy
include helpers  # Include helpers.nim from same directory

proc greet(name: string): string {.exportpy.} =
  return make_greeting(name)

proc add(a: int, b: int): int {.exportpy.} =
  return a + b
```

**nim/helpers.nim:**
```nim
proc make_greeting(name: string): string =
  return "Hello, " & name & "!"
```

Compile `my_package_lib.nim` and both modules are included in the final `.so`/`.pyd` file.

**Important**: Use `include` (not `import`) when building shared libraries. The `include` directive literally includes the code at compile time, while `import` creates a separate module namespace.

## Output Location

The `output-location` setting controls where the compiled extension is placed:

- **`"auto"`** (default): Uses flat layout - places extension in `{module_name}/`

- **`"src"`**: Explicitly uses `src/{module_name}/` (for compatibility with old projects)

- **Explicit path**: Use a custom output directory

## Python Usage

Once compiled and installed, use your Nim extension like any Python module:

```python
import my_package

# Call Nim-compiled functions (imported via __init__.py)
result = my_package.greet("World")
print(result)  # "Hello, World!"

sum_result = my_package.add(5, 10)
print(sum_result)  # 15
```

## How It Works

1. **Validation**: Checks Nim compiler is installed and config is valid
2. **Source Discovery**: Finds Nim files in the configured directory
3. **Entry Point Detection**: Identifies the main entry point file
4. **Compilation**: Invokes `nim c --app:lib` with appropriate flags
5. **Module Path**: Adds `--path:{nim_dir}` so includes work between files
6. **Output**: Generates proper `{lib_name}.so` (Linux/Mac) or `{lib_name}.pyd` (Windows) in the module directory
7. **Ready to use**: Module is immediately importable from the project root

## For Maintainers: Publishing Releases

### Creating a Release

To publish a new version of nuwa-build to PyPI:

1. **Update the version** in `pyproject.toml`:
   ```toml
   version = "0.2.0"  # Bump version
   ```

2. **Create a git tag**:
   ```bash
   git tag v0.2.0
   git push origin v0.2.0
   ```

3. **GitHub Actions will automatically**:
   - Build the package (both wheel and source distribution)
   - Publish to PyPI using trusted publishing

### Setting Up PyPI Trusted Publishing

First time setup (one-time):

1. Go to https://pypi.org/manage/account/publishing/
2. Add a new publisher:
   - **PyPI Project Name**: `nuwa-build`
   - **Owner**: Your GitHub username
   - **Repository name**: `nuwa-build`
   - **Workflow name**: `publish.yml`
   - **Environment name**: `pypi`

3. GitHub Actions will now be able to publish to PyPI without storing API tokens!

### Manual Publishing (if needed)

If you need to publish manually:

```bash
# Build
python -m build

# Publish (requires twine)
pip install twine
twine upload dist/*
```

## Development

### Setting Up for Development

```bash
# Clone the repo
git clone https://github.com/martineastwood/nuwa-build
cd nuwa-build

# Install in development mode
pip install -e .

# Install nimpy if needed
nimble install nimpy

# Run tests
# (tests not yet implemented)
```

### Architecture

Nuwa Build is organized into several modules:

- **`config.py`** - Configuration parsing and validation
- **`discovery.py`** - Source file discovery
- **`utils.py`** - Utility functions (platform detection, validation)
- **`wheel_utils.py`** - Wheel building helpers
- **`backend.py`** - Core compilation and PEP 517/660 hooks
- **`cli.py`** - Command-line interface

### Contributing

Contributions are welcome! The codebase is well-organized with:
- Full type hints
- Comprehensive error handling
- Proper logging support
- Context managers for resource management

## Troubleshooting

### "Nim compiler not found"

Make sure Nim is installed and in your PATH:

```bash
nim --version
```

Install from https://nim-lang.org/install.html if needed.

### "cannot open file: nimpy"

You need to install the nimpy library. You can either:

**Option 1: Auto-install via configuration** (Recommended)
```toml
[tool.nuwa]
nimble-deps = ["nimpy"]
```

**Option 2: Manual installation**
```bash
nimble install nimpy
```

### "nimble package manager not found"

Nimble is installed with Nim. Make sure Nim is properly installed and in your PATH:

```bash
nim --version
nimble --version
```

If nimble is not found, reinstall Nim from https://nim-lang.org/install.html.

### "ModuleNotFoundError: No module named 'my_package'"

The module needs to be compiled first. Run:

```bash
nuwa develop
```

Then you can import it directly from the project root. No `pip install` needed!

**For pytest**: Make sure you've compiled the extension with `nuwa develop` first. The flat layout allows pytest to discover the module automatically.

### "ValueError: Module name '...' is not a valid Python identifier"

Your project name contains invalid characters for Python modules. Module names can only contain letters, numbers, and underscores, and cannot start with a number. Use the `--name` option:

```bash
nuwa new my-project --name my_valid_name
```

### "Multiple .nim files found in nim/"

Nuwa found multiple `.nim` files but can't determine which is the entry point. Specify it in `pyproject.toml`:

```toml
[tool.nuwa]
entry-point = "my_entry_file.nim"
```

Or ensure there's only one `.nim` file, or name your entry point `{module_name}_lib.nim`.

## License

MIT

## Acknowledgments

- Uses [nimpy](https://github.com/yglukhov/nimpy) for Python bindings
- Named after [Nüwa](https://en.wikipedia.org/wiki/N%C3%BCwa), the Chinese goddess of creation
