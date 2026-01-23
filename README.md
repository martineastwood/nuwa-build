# Nuwa Build

Build Python extensions with Nim using zero-configuration tooling.

## Status

🚧 **Work In Progress:** This library is currently under active development. APIs may change, and things might break. Use at your own risk!

## Features

- **Zero Configuration**: Works out of the box with sensible defaults
- **Multi-file Projects**: Compile multiple Nim files into a single Python extension
- **Flexible Configuration**: Configure via `pyproject.toml` or CLI arguments
- **PEP 517/660 Compatible**: Build wheels and source distributions
- **Build Command**: `nuwa build` for easy local wheel creation
- **Cross-Platform CI**: Template includes GitHub Actions workflow with manylinux support
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

- Python 3.9+ (including Python 3.14 with free-threaded ABI support)
- Nim compiler (must be installed and available in your PATH)
- nimpy library (install via `nimble install nimpy`)

**Python Version Support**:

Nuwa Build supports all Python versions from 3.9 onwards, including Python 3.14 with free-threaded (GIL-less) execution. The build system automatically detects and uses the correct ABI tags for your Python version, including `cp314t` for free-threaded builds.

## Quick Start

### Create a New Project

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

### Build and Test

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

**Note**: No `pip install -e .` needed due to flat project layout. You can run `python example.py` and `pytest` directly after compiling the default template project.

### 🤖 AI-Assisted Development

This project includes a `skill.md` file designed to teach AI coding agents (Cursor, Antigravity, Copilot, etc.) how to work with Nuwa Build.

**Why use it?**

Standard LLMs often assume Python extensions require `setup.py` or `pip install -e .`. The `skill.md` file provides your agent with the correct context to:

- **Understand the flat layout:** Knows that `.so` files are generated directly in the package directory.
- **Use correct commands:** Enforces `nuwa develop` and `nuwa watch` instead of standard pip commands.
- **Write correct Nim:** Reminds the agent to use `include` for shared libraries and `{.nuwa_export.}` for bindings (which automatically generates type stubs).

**How to use:**

1. **Claude Code:** Copy the `skill.md` file into `~/.claude/skills/nuwa-build/` for global use or `<workspace-root>/.claude/skills/nuwa-build/` for project-specific use.
2. **Antigravity:** Copy the `skill.md` file into `~/.gemini/antigravity/skills/nuwa-build/` for global use or `<workspace-root>/.agent/skills/nuwa-build/` for project-specific use.
3. **Cursor:** Copy the `skill.md` file into `~/.cursor/skills/nuwa-build/` for global use or `<workspace-root>/.cursor/skills/nuwa-build/` for project-specific use.
4. **General Chat:** Upload or paste `skill.md` into your context window when starting a new session.

### Watch Mode

For development, use watch mode to automatically recompile when you change Nim files:

```bash
# Watch for changes and auto-recompile
nuwa watch

# Watch with tests after each compile
nuwa watch --run-tests

# Watch in release mode
nuwa watch --release
```

## Jupyter Notebook Support

Nuwa-Build includes a Jupyter magic command for compiling Nim code directly in notebooks.

### Usage

```python
# Load the extension
%load_ext nuwa_build.magic

# Compile Nim code in a cell
%%nuwa
proc add(a, b: int): int {.exportpy.} =
    return a + b

# Use the function immediately (no import needed!)
add(1, 2)  # Output: 3
```

### Caching

Nuwa automatically caches compiled modules in `.nuwacache/`:

- **Cache hits**: Re-running cells uses cached compilation (fast!)
- **Cache misses**: New code or different flags trigger recompilation
- **Persistent**: Cache survives kernel restarts

#### Cache Management

```python
# Show cache statistics
%nuwa_cache_info
# Output: 📊 Cache: 3 modules, 123.4 KB
#         📍 Location: /path/to/.nuwacache

# Clear cache (e.g., to force rebuild or free space)
%nuwa_clean
# Output: 🧹 Cleared cache: .nuwacache
```

Or manually delete the `.nuwacache/` folder.

#### .gitignore

Add to your `.gitignore`:

```
.nuwacache/
```

### Compiler Flags

Pass Nim compiler flags on the magic line:

```python
%%nuwa -d:release --opt:speed
proc optimized_func(n: int): int {.exportpy.} =
    # Optimized implementation
    ...
```

Different flags create different cache entries (code hash includes flags).

### Example

```python
# Cell 1: Load extension
%load_ext nuwa_build.magic

# Cell 2: Compile simple function
%%nuwa
proc greet(name: string): string {.exportpy.} =
    return "Hello, " & name & "!"

# Cell 3: Use immediately
print(greet("World"))  # Output: Hello, World!

# Cell 4: Multiple functions
%%nuwa
proc add(a, b: int): int {.exportpy.} = a + b
proc multiply(a, b: int): int {.exportpy.} = a * b

print(add(5, 3))      # 8
print(multiply(4, 7)) # 28

# Cell 5: With compiler flags
%%nuwa -d:release
proc fibonacci(n: int): int {.exportpy.} =
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

print(fibonacci(10))  # 55 (optimized)
```

### Install and Distribute

```bash
# Build a wheel for distribution
nuwa build

# Build and install locally
pip install dist/*.whl

# Build using standard Python tools (alternative)
pip install . --no-build-isolation

# Build source distribution
python -m build
```

## Continuous Integration with GitHub Actions

The `nuwa new` template includes a pre-configured GitHub Actions workflow (`.github/workflows/publish.yml`) for automated cross-platform wheel building and PyPI publishing.

### What's Included

The workflow uses a custom composite action (`martineastwood/nuwa-build-action@v1`) that integrates with [cibuildwheel](https://github.com/pypa/cibuildwheel) to build wheels across:

- **Platforms**: Linux (manylinux), macOS, Windows
- **Python versions**: 3.9, 3.10, 3.11, 3.12, 3.13, 3.14
- **Architectures**: x86_64, arm64 (Apple Silicon)

### How It Works

The custom action handles platform-specific Nim compiler installation:

| Platform | Installation Method |
|----------|-------------------|
| **Linux** | Installs Nim in Docker container via tar.xz |
| **Windows** | Uses Chocolatey (`choco install nim`) |
| **macOS** | Uses choosenim installer |

### First-Time Setup

1. **Configure Trusted Publishing** on PyPI:
   - Go to https://pypi.org/manage/account/publishing/
   - Add a new publisher with:
     - PyPI Project Name: Your package name
     - Owner: Your GitHub username/organization
     - Repository name: Your repository name
     - Workflow name: `publish.yml`

2. **Push a version tag** to trigger the workflow:
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```

### Manual Workflow Trigger

You can also manually trigger the workflow from the GitHub Actions tab in your repository, useful for testing CI before release.

### Customization

To customize the build (e.g., different Nim version or cibuildwheel version), edit `.github/workflows/publish.yml`:

```yaml
- name: Build wheels
  uses: martineastwood/nuwa-build-action@v1
  with:
    nim-version: "2.2.0"      # Nim version to install
    cibw-version: "2.22.0"     # cibuildwheel version
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

# Build profiles (predefined compiler flag sets)
[tool.nuwa.profiles.dev]
nim-flags = ["-d:debug", "--debugger:native", "--linenos:on"]

[tool.nuwa.profiles.release]
nim-flags = ["-d:release", "--opt:speed", "--stacktrace:off"]

[tool.nuwa.profiles.bench]
nim-flags = ["-d:release", "--opt:speed", "--stacktrace:on"]

[tool.nuwa.profiles.size]
nim-flags = ["-d:release", "--opt:size"]
```

### Configuration Options

| Option            | Type   | Default                   | Description                                                    |
| ----------------- | ------ | ------------------------- | -------------------------------------------------------------- |
| `nim-source`      | string | `"nim"`                   | Directory containing Nim source files                          |
| `module-name`     | string | Derived from project name | Python package name                                            |
| `lib-name`        | string | `{module_name}_lib`       | Internal compiled extension name                               |
| `entry-point`     | string | `{lib_name}.nim`          | Main entry point file (relative to `nim-source`)               |
| `output-location` | string | `"auto"`                  | Where to place compiled extension (`"auto"`, `"src"`, or path) |
| `nim-flags`       | list   | `[]`                      | Additional compiler flags                                      |
| `nimble-deps`     | list   | `[]`                      | Nimble packages to auto-install before build                   |
| `profiles`        | table  | `{}`                      | Predefined build profiles with preset compiler flags           |

**Note**: The entry point filename determines the Python module name of the compiled extension. If your entry point is `my_package_lib.nim`, the module will be importable as `my_package_lib`.

### Build Profiles

Build profiles allow you to define preset compiler flag configurations for different scenarios:

```toml
[tool.nuwa.profiles.dev]
nim-flags = ["-d:debug", "--debugger:native", "--linenos:on"]

[tool.nuwa.profiles.release]
nim-flags = ["-d:release", "--opt:speed", "--stacktrace:off"]

[tool.nuwa.profiles.bench]
nim-flags = ["-d:release", "--opt:speed", "--stacktrace:on"]
```

**Usage:**
```bash
nuwa develop --profile dev
nuwa build --profile release
nuwa watch --profile bench
```

**Flag precedence:**
1. Base `nim-flags` from `[tool.nuwa]`
2. Profile flags (appended)
3. CLI `--nim-flag` arguments (applied last, for maximum flexibility)

### Shell Completion

Nuwa supports shell completion for bash, zsh, and fish via the `shtab` library.

**Installation:**
```bash
# Install shtab (optional dev dependency)
pip install shtab

# Generate and install completions
nuwa --print-completion bash > ~/.local/share/bash-completion/completions/nuwa
nuwa --print-completion zsh > ~/.zfunc/_nuwa
nuwa --print-completion fish > ~/.config/fish/completions/nuwa.fish
```

**For zsh users**, add to your `~/.zshrc`:
```bash
# Add completion function path
fpath=(~/.zfunc $fpath)
autoload -U compinit && compinit
```

Completions work automatically for all commands, flags, and will suggest files/directories where appropriate.

## Package Data

Nuwa automatically includes all non-Python files in your package directory (config files, data files, templates, etc.) when building wheels.

### Automatic Inclusion (Default)

By default, all files in your package directory are included in the wheel, except for:

- Python cache (`__pycache__`, `*.pyc`, `*.pyo`)
- Compiled extensions (`.so`, `.pyd`, `.dll` - added separately)
- Version control (`.git`, `.hg`, `.svn`)
- Build artifacts (`dist/`, `build/`, `*.egg-info`)
- Development caches (`.pytest_cache`, `.mypy_cache`, `.ruff_cache`)
- IDE files (`.vscode`, `.idea`, `.DS_Store`)
- Test directories (`tests/`, `test/`)

**Example project structure:**
```
my_package/
├── __init__.py          # Python wrapper
├── my_package_lib.so    # Compiled Nim extension (generated)
├── config.json          # ✅ Included in wheel
├── data.csv             # ✅ Included in wheel
├── models/
│   └── model.bin        # ✅ Included in wheel
└── templates/
    └── template.html    # ✅ Included in wheel
```

### Fine-Grained Control with MANIFEST.in

For precise control over what's included in your wheel, create a `MANIFEST.in` file in your project root:

```
include package/config.json
recursive-include package/templates *.html *.css *.js
global-include *.md
exclude package/dev_config.yaml
recursive-exclude package/tests *.py
```

**Supported commands:**

- `include pattern ...` - Include files matching patterns
- `exclude pattern ...` - Exclude files matching patterns
- `recursive-include dir pattern ...` - Include files in directory matching patterns
- `recursive-exclude dir pattern ...` - Exclude files in directory matching patterns
- `global-include pattern ...` - Include files anywhere matching patterns
- `global-exclude pattern ...` - Exclude files anywhere matching patterns

**Common examples:**

```bash
# Include specific config file
include package/production.json

# Exclude development configs
exclude package/*-dev.yaml
exclude package/config.local.*

# Include all templates
recursive-include package/templates *

# Include but exclude test data
recursive-include package/data *.csv
recursive-exclude package/data test-*.csv

# Include documentation
global-include *.md
global-include LICENSE
```

**Note:** If `MANIFEST.in` doesn't exist, all package data is included automatically (smart defaults).

## CLI Commands

### `nuwa new <path>`

Create a new project scaffold:

```bash
nuwa new my_project
nuwa new my_project --name custom-name
```

### `nuwa init [path]`

Initialize Nuwa in an existing project:

```bash
# Initialize in current directory
nuwa init

# Initialize in specific directory
nuwa init /path/to/project
```

This command:

- Adds `[build-system]` and `[tool.nuwa]` to `pyproject.toml` (or creates it if missing)
- Creates `nim/` directory with entry point and helper files
- Updates `.gitignore` with build artifacts
- Non-destructive: won't overwrite existing files

Use this when you have an existing Python project and want to add Nim extensions to it.

### `nuwa develop`

Compile the project in-place:

```bash
# Debug build
nuwa develop

# Release build
nuwa develop --release

# Use build profile
nuwa develop --profile dev
nuwa develop --profile release

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

# Watch with build profile
nuwa watch --profile bench

# Override configuration
nuwa watch --module-name my_module
nuwa watch --nim-source my_nim_dir
```

### `nuwa build`

Build a wheel package for distribution:

```bash
# Build a wheel (output: dist/)
nuwa build

# Build with custom Nim flags
nuwa build --nim-flag="-d:release" --nim-flag="--opt:speed"

# Build with profile
nuwa build --profile release

# Override configuration
nuwa build --module-name my_module
nuwa build --nim-source my_nim_dir
nuwa build --entry-point main.nim
nuwa build --output-dir build/
```

**Note**: The `nuwa build` command creates wheels in the `dist/` directory, following standard Python packaging conventions. This is the recommended way to build wheels for distribution instead of using `pip wheel` or `python -m build`.

### `nuwa clean`

Clean build artifacts and dependencies:

```bash
# Clean everything (dependencies + artifacts)
nuwa clean

# Clean only dependencies (.nimble/ directory)
nuwa clean --deps

# Clean only build artifacts and cache
nuwa clean --artifacts
```

**What gets cleaned:**

- `--deps`: Removes the `.nimble/` directory (local Nimble packages)
- `--artifacts`: Removes `nimcache/`, `build/`, `dist/` directories and compiled `.so`/`.pyd` files
- (no flags): Cleans both dependencies and artifacts

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
import nuwa_sdk  # Provides nuwa_export for automatic type stub generation
include helpers  # Include helpers.nim from same directory

proc greet(name: string): string {.nuwa_export.} =
  return make_greeting(name)

proc add(a: int, b: int): int {.nuwa_export.} =
  return a + b
```

**nim/helpers.nim:**

```nim
proc make_greeting(name: string): string =
  return "Hello, " & name & "!"
```

Compile `my_package_lib.nim` and both modules are included in the final `.so`/`.pyd` file.

**Important**: Use `include` (not `import`) when building shared libraries. The `include` directive literally includes the code at compile time, while `import` creates a separate module namespace.

### Exporting Functions to Python

**You must add the `{.nuwa_export.}` pragma to any Nim procedure you want to access from Python.**

- ✅ **Exported**: `proc add(a: int, b: int): int {.nuwa_export.}` - Accessible from Python
- ❌ **Not exported**: `proc add(a: int, b: int): int` - Not accessible from Python

The `{.nuwa_export.}` pragma does two things:

1. Makes the function callable from Python (via the underlying nimpy library)
2. Generates type stub information for IDE autocomplete and type checking

**Common mistake**: Forgetting the pragma means your function won't be available in Python, even though it compiles successfully.

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

### Contributing

Contributions are welcome! The codebase is well-organized with:

- Full type hints and mypy validation
- Comprehensive error handling
- Proper logging support
- Context managers for resource management
- Clear module boundaries and separation of concerns

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
