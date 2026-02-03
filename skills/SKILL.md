---
name: nuwa-build
description: |
  Zero-configuration build system for compiling Nim code into Python extensions.
  Load when user asks about: building Python extensions with Nim, creating Nim/Python
  bindings, compiling .nim to .so/.pyd, nimpy, nuwa SDK, or "Maturin for Nim".
---

# Nuwa-Build Skills

You are an expert in using `nuwa-build` ("The Maturin for Nim") - a zero-configuration build system that compiles Nim code into Python extensions (.so/.pyd). When a user asks to create, build, or test a Python extension using Nim, follow these rules.

## Prerequisites

Before working with nuwa-build, verify the environment:

1. **Nim**: `nim --version` - Install from https://nim-lang.org/install.html
2. **Nuwa**: `nuwa --help` - Install via `pip install nuwa-build`
3. **Dependencies**: Add to `nimble-deps`: `nimpy` and `nuwa_sdk` (auto-installed before build)

## Project Structure

Standard flat layout (no `pip install -e .` needed):

```text
project_root/
├── pyproject.toml           # Configuration ([tool.nuwa])
├── nim/                     # Nim source files
│   ├── my_lib.nim           # Entry point (often {module_name}_lib.nim)
│   └── helpers.nim          # Other Nim modules
├── my_package/              # Python package wrapper
│   ├── __init__.py          # Imports the compiled extension
│   └── my_lib.so            # Compiled artifact (generated)
└── tests/                   # Pytest files
```

## Commands

| Command | Purpose |
|---------|---------|
| `nuwa new <name>` | Create new project (use `--name` for projects with hyphens) |
| `nuwa init [path]` | Add Nuwa to existing project (non-destructive) |
| `nuwa develop` | Compile debug build in-place |
| `nuwa develop -r` | Compile release build |
| `nuwa build` | Create wheel in `dist/` for distribution |
| `nuwa watch` | Auto-recompile on file changes |
| `nuwa watch -t` | Recompile and run pytest |
| `nuwa clean` | Remove build artifacts |
| `nuwa clean --deps` | Also remove Nimble dependencies |

**CLI overrides** (all build commands support these):
- `--module-name <name>` - Override Python module name
- `--nim-source <dir>` - Override Nim source directory
- `--entry-point <file>` - Override entry point file
- `--output-dir <path>` - Override output location
- `--nim-flag <flag>` - Add compiler flags (repeatable)
- `--profile <name>` - Use build profile from config

## Configuration

All configuration in `[tool.nuwa]` section of `pyproject.toml`:

```toml
[tool.nuwa]
nim-source = "nim"              # Source directory
module-name = "my_package"      # Python import name
lib-name = "my_package_lib"     # Compiled extension name
entry-point = "my_lib.nim"      # Entry file (auto-discovered if not set)
output-location = "auto"        # "auto", "src", or custom path
nim-flags = []                  # Additional compiler flags
nimble-deps = ["nimpy", "nuwa_sdk"]  # Auto-installed dependencies
bindings = "nimpy"              # Python bindings framework

# Build profiles - predefined compiler flag sets
[tool.nuwa.profiles.dev]
nim-flags = ["-d:debug", "--debugger:native", "--linenos:on", "--stacktrace:on"]

[tool.nuwa.profiles.release]
nim-flags = ["-d:release", "--opt:speed", "--stacktrace:off", "--checks:off"]

[tool.nuwa.profiles.bench]
nim-flags = ["-d:release", "--opt:speed", "--stacktrace:on"]
```

**Flag precedence**: Base `nim-flags` → Profile flags → CLI `--nim-flag` arguments

## Entry Point Discovery

Auto-discovery priority order:
1. Explicit `entry-point` in `[tool.nuwa]`
2. `{lib_name}.nim` (e.g., `my_package_lib.nim`)
3. `lib.nim`
4. Single `.nim` file if only one exists
5. Error if multiple files found

**Best practice**: Name entry point `{module_name}_lib.nim`

## Writing Nim for Python

**Dependencies**: Add to `nimble-deps`: `["nimpy", "nuwa_sdk"]`

```nim
import nuwa_sdk  # Required for {.nuwa_export.} pragma and type stubs

proc add(a: int, b: int): int {.nuwa_export.} =
  return a + b

proc greet(name: string): string {.nuwa_export.} =
  return "Hello, " & name & "!"
```

**Python wrapper** (`__init__.py`):
```python
from .my_package_lib import *
__version__ = "0.1.0"
```

## Multi-File Projects

Use `include` (not `import`) for shared libraries:

```nim
# nim/my_lib.nim
import nuwa_sdk
include helpers  # Includes helpers.nim at compile time

proc greet(name: string): string {.nuwa_export.} =
  return make_greeting(name)
```

**Why `include`?** Creates single compilation unit. All files compiled into one `.so`/`.pyd`.

## Package Data

Nuwa automatically includes non-Python files from your package (config, data, templates, etc.) except cache/build artifacts. For fine-grained control, create `MANIFEST.in`:

```
include package/config.json
recursive-include package/templates *.html
exclude package/*-dev.yaml
```

Most projects don't need this - default behavior works well.

## Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| "Nim compiler not found" | Nim not installed or not in PATH | Install from https://nim-lang.org/install.html |
| "ModuleNotFoundError: No module named 'my_package'" | Extension not compiled | Run `nuwa develop` |
| "cannot open file: nimpy" or "cannot open file: nuwa_sdk" | Dependencies not installed | Add to `nimble-deps` in config |
| "Multiple .nim files found in nim/" | Entry point unclear | Set `entry-point` in config or rename to `{module_name}_lib.nim` |
| "Module name '...' is not a valid Python identifier" | Project name has hyphens | Use `nuwa new my-project --name valid_name` |

## AI Agent Guidelines

When helping users with nuwa-build:

1. **Check prerequisites first** - Run `nim --version` before attempting builds
2. **Use `nuwa develop` for development** - Not `pip install` or `python setup.py build`
3. **Use `nuwa build` for distribution** - Creates wheels in `dist/`, preferred over `pip wheel`
4. **Prefer `nuwa watch --run-tests`** - Provides fast feedback for iterative development
5. **Check existing config first** - Read `[tool.nuwa]` in `pyproject.toml` before suggesting changes
6. **Use `include` for multi-file Nim projects** - Not `import`
7. **Auto-install dependencies** - Add to `nimble-deps` rather than manual `nimble install`
8. **Test after building** - Run `pytest` after `nuwa develop` completes
9. **Use build profiles** - Recommend profiles over ad-hoc `--nim-flag` usage

## Optional Features

**Shell Completion**: Requires `pip install shtab`, then run `nuwa --print-completion bash|zsh|fish`

**Version-specific dependencies**: `nimble-deps = ["nimpy", "cligen >= 1.0.0", "arraymancer@#head"]`

**GitHub Actions**: Projects created with `nuwa new` include automated PyPI publishing workflow using Trusted Publishing. Configure at https://pypi.org/manage/account/publishing/ then push tags to trigger builds.
