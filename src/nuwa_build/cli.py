"""Command-line interface for Nuwa Build."""

import argparse
import builtins
import contextlib
import logging
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from . import __version__
from .backend import _compile_nim
from .config import ConfigResolver, parse_nuwa_config
from .constants import DEFAULT_DEBOUNCE_DELAY
from .pep517_hooks import build_wheel
from .templates import (
    BUILD_SYSTEM_SECTION,
    EXAMPLE_PY,
    GITHUB_ACTIONS_PUBLISH_YML,
    GITIGNORE,
    HELPERS_NIM,
    INIT_PY,
    LIB_NIM,
    PYPROJECT_TOML,
    README_MD,
    TEST_PY,
    TOOL_NUWA_SECTION,
)
from .utils import normalize_package_name

logger = logging.getLogger("nuwa")


def format_error(error: Exception) -> str:
    """Format an exception with consistent error message style.

    Args:
        error: The exception to format

    Returns:
        Formatted error message string
    """
    error_type = type(error).__name__

    if isinstance(error, FileNotFoundError):
        return f"❌ Error: {error}"
    elif isinstance(error, ValueError):
        return f"❌ Configuration Error: {error}"
    elif isinstance(error, subprocess.CalledProcessError):
        # Error already formatted and printed by backend.py
        return ""
    elif isinstance(error, RuntimeError):
        return f"❌ Error: {error}"
    elif isinstance(error, OSError):
        return f"❌ System Error: {error}"
    else:
        return f"❌ Unexpected Error ({error_type}): {error}"


def handle_cli_error(error: Exception, context: str = "") -> None:
    """Handle CLI errors with consistent formatting and exit.

    Args:
        error: The exception that occurred
        context: Optional context about what operation was being performed
    """
    error_msg = format_error(error)
    if error_msg:
        print(error_msg)

    if not isinstance(
        error,
        (
            FileNotFoundError,
            ValueError,
            subprocess.CalledProcessError,
            RuntimeError,
            OSError,
        ),
    ):
        # Log unexpected errors with full traceback
        logger.error(f"{context}: {error}", exc_info=True)

    sys.exit(1)


def safe_run_command(command_func):
    """Decorator to handle errors consistently in CLI commands.

    Args:
        command_func: The CLI command function to wrap

    Returns:
        Wrapped function with consistent error handling
    """

    def wrapper(args: argparse.Namespace):
        try:
            return command_func(args)
        except Exception as e:
            handle_cli_error(e, context=f"Error in {command_func.__name__}")

    return wrapper


def validate_project_name(name: str) -> None:
    """Validate project name for safety and Python compatibility.

    Args:
        name: Project name to validate

    Raises:
        ValueError: If name is invalid
    """
    if not name:
        raise ValueError("Project name cannot be empty")

    # Check for reasonable length
    if len(name) > 100:
        raise ValueError("Project name is too long (max 100 characters)")

    # Check for valid characters (alphanumeric, hyphen, underscore)
    if not re.match(r"^[a-zA-Z0-9_-]+$", name):
        raise ValueError("Project name can only contain letters, numbers, hyphens, and underscores")

    # Check it doesn't start with a digit or hyphen
    if name[0].isdigit() or name[0] == "-":
        raise ValueError("Project name must start with a letter or underscore")

    # Check for Python keywords (after normalization)
    module_name = normalize_package_name(name)
    if module_name in sys.modules or hasattr(builtins, module_name):
        raise ValueError(
            f"Project name '{name}' conflicts with Python keyword/builtin '{module_name}'"
        )


def validate_path(path: Path) -> None:
    """Validate path is safe for project creation.

    Args:
        path: Path to validate

    Raises:
        ValueError: If path is invalid or unsafe
    """
    # Resolve the path to check for directory traversal
    try:
        resolved = path.resolve()
    except Exception as e:
        raise ValueError(f"Invalid path '{path}': {e}") from None

    # Check if parent directory exists
    if not resolved.parent.exists():
        raise ValueError(
            f"Parent directory does not exist: {resolved.parent}\n"
            f"Please create the parent directory first."
        )

    # Check if path is within parent (no directory traversal)
    # Check if path is within parent (no directory traversal)
    with contextlib.suppress(ValueError):
        resolved.relative_to(resolved.parent.parent)

    # Warn if path is absolute (usually not what users want for 'nuwa new')
    if path.is_absolute():
        print(f"⚠️  Warning: Using absolute path '{path}'")


def validate_module_name(module_name: str) -> None:
    """Validate Python module name is valid.

    Args:
        module_name: Module name to validate

    Raises:
        ValueError: If module name is invalid
    """
    if not module_name:
        raise ValueError("Module name cannot be empty")

    # Check Python module naming rules
    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", module_name):
        raise ValueError(
            f"Module name '{module_name}' is not a valid Python identifier.\n"
            "Module names must start with a letter or underscore and contain only letters, numbers, and underscores."
        )


def build_config_overrides(args: argparse.Namespace) -> Optional[dict]:
    """Build config overrides from CLI args.

    Args:
        args: Parsed command-line arguments

    Returns:
        Dictionary of config overrides, or None if no overrides provided
    """
    config_overrides: dict = {}
    if args.module_name:
        config_overrides["module_name"] = args.module_name
    if args.nim_source:
        config_overrides["nim_source"] = args.nim_source
    if args.entry_point:
        config_overrides["entry_point"] = args.entry_point
    if args.output_dir:
        config_overrides["output_location"] = args.output_dir
    if args.nim_flags:
        config_overrides["nim_flags"] = args.nim_flags

    return config_overrides if config_overrides else None


def run_new(args: argparse.Namespace) -> None:
    """Create a new Nuwa project.

    Args:
        args: Parsed command-line arguments
    """
    path = Path(args.path)

    # Validate inputs
    validate_path(path)
    name = args.name if args.name else path.name
    validate_project_name(name)

    module_name = normalize_package_name(name)  # Python import safety
    lib_name = f"{module_name}_lib"  # Compiled extension module name

    # Validate module name
    validate_module_name(module_name)

    if path.exists() and any(path.iterdir()):
        sys.exit(f"❌ Error: Directory '{path}' is not empty.")

    print(f"✨ Creating new Nuwa project: {name}")

    # Create directory structure
    (path / "nim").mkdir(parents=True, exist_ok=True)
    (path / module_name).mkdir(parents=True, exist_ok=True)
    (path / "tests").mkdir(parents=True, exist_ok=True)
    (path / ".github" / "workflows").mkdir(parents=True, exist_ok=True)

    # Write pyproject.toml
    with open(path / "pyproject.toml", "w", encoding="utf-8") as f:
        f.write(PYPROJECT_TOML.format(project_name=name, module_name=module_name))

    # Write Nim sources - entry point filename determines Python module name
    with open(path / "nim" / f"{lib_name}.nim", "w", encoding="utf-8") as f:
        f.write(LIB_NIM.format(module_name=module_name))

    with open(path / "nim" / "helpers.nim", "w", encoding="utf-8") as f:
        f.write(HELPERS_NIM.format(module_name=module_name))

    # Write Python package with __init__.py
    with open(path / module_name / "__init__.py", "w", encoding="utf-8") as f:
        f.write(INIT_PY.format(module_name=module_name))

    # Write README
    with open(path / "README.md", "w", encoding="utf-8") as f:
        f.write(README_MD.format(project_name=name, module_name=module_name))

    # Write supporting files
    with open(path / ".gitignore", "w", encoding="utf-8") as f:
        f.write(GITIGNORE)

    # Write GitHub Actions workflow
    with open(path / ".github" / "workflows" / "publish.yml", "w", encoding="utf-8") as f:
        f.write(GITHUB_ACTIONS_PUBLISH_YML)

    with open(path / "example.py", "w", encoding="utf-8") as f:
        f.write(EXAMPLE_PY.format(module_name=module_name))

    # Write test file
    with open(path / "tests" / f"test_{module_name}.py", "w", encoding="utf-8") as f:
        f.write(TEST_PY.format(module_name=module_name))

    print(f"✅ Ready! \n   cd {path}\n   nuwa develop\n   python example.py\n   pytest")


def run_develop(args: argparse.Namespace) -> None:
    """Compile the project in-place.

    Args:
        args: Parsed command-line arguments
    """
    build_type = "release" if args.release else "debug"
    config_overrides = build_config_overrides(args)

    _compile_nim(
        build_type=build_type,
        inplace=True,
        config_overrides=config_overrides,
    )
    # Note: Success message is printed by backend.py
    print("💡 Module updated. Run your tests or scripts to verify.")


def run_build(args: argparse.Namespace) -> None:
    """Build a wheel package.

    Args:
        args: Parsed command-line arguments
    """

    config_overrides = build_config_overrides(args)

    # Setup output directory
    dist_dir = Path.cwd() / "dist"

    # Create dist directory if it doesn't exist
    dist_dir.mkdir(parents=True, exist_ok=True)

    # Build the wheel with config overrides
    config_settings = {"config_overrides": config_overrides} if config_overrides else None
    print("🔨 Building wheel...")
    wheel_filename = build_wheel(str(dist_dir), config_settings=config_settings)

    # Construct full path for user feedback
    wheel_path = dist_dir / wheel_filename

    # Calculate file size for nicer output
    size_kb = wheel_path.stat().st_size / 1024

    print(f"✅ Successfully built: {wheel_filename}")
    print(f"   Location: {wheel_path}")
    print(f"   Size: {size_kb:.1f} KB")
    print(f"💡 Install with: pip install {wheel_path}")


def run_clean(args: argparse.Namespace) -> None:
    """Clean build artifacts and dependencies.

    Args:
        args: Parsed command-line arguments
    """

    cleaned = []
    errors = []

    # Determine what to clean based on flags
    clean_all = not (args.deps or args.artifacts)

    # Helper to safely remove a directory
    def safe_remove_dir(path: Path, name: str) -> None:
        """Safely remove a directory if it exists."""
        if path.exists() and path.is_dir():
            try:
                shutil.rmtree(path)
                cleaned.append(f"{name}/")
            except Exception as e:
                errors.append(f"{name}/: {e}")

    # Helper to safely remove a file
    def safe_remove_file(path: Path) -> None:
        """Safely remove a file if it exists and is not a symlink."""
        if path.exists() and path.is_file():
            # Skip symlinks to avoid deleting the target
            if path.is_symlink():
                return
            try:
                path.unlink()
                # Try to get relative path, fall back to absolute if it fails
                try:
                    display_path = str(path.relative_to(Path.cwd()))
                except ValueError:
                    display_path = str(path)
                cleaned.append(display_path)
            except Exception as e:
                errors.append(f"{path}: {e}")

    # Clean .nimble/ directory
    if clean_all or args.deps:
        safe_remove_dir(Path.cwd() / ".nimble", ".nimble")

    # Clean nimcache/ directory
    if clean_all or args.artifacts:
        safe_remove_dir(Path.cwd() / "nimcache", "nimcache")

    # Clean build/ directory
    if clean_all or args.artifacts:
        safe_remove_dir(Path.cwd() / "build", "build")

    # Clean dist/ directory
    if clean_all or args.artifacts:
        safe_remove_dir(Path.cwd() / "dist", "dist")

    # Clean compiled artifacts - only in Nuwa-managed locations
    if clean_all or args.artifacts:
        try:
            config = parse_nuwa_config()
            lib_name = config.get("lib_name", "")
            module_name = config.get("module_name", "")
            ext = ".pyd" if sys.platform == "win32" else ".so"

            # Only remove the specific compiled extension that Nuwa generates
            if lib_name:
                # Check in common output locations
                for output_dir in [Path(module_name), Path("src") / module_name]:
                    if output_dir.exists():
                        ext_file = output_dir / f"{lib_name}{ext}"
                        safe_remove_file(ext_file)

        except FileNotFoundError as e:
            # pyproject.toml not found - not a Nuwa project
            logger.debug(f"No pyproject.toml found, skipping artifact cleaning: {e}")
            errors.append(
                "Could not load pyproject.toml (not a Nuwa project?). "
                "Skipping compiled artifact cleanup."
            )
        except KeyError as e:
            # Config missing required fields
            logger.warning(f"Config missing required field for artifact cleaning: {e}")
            errors.append(f"Config error: missing field {e}. Skipping artifact cleanup.")
        except Exception as e:
            # Log the full error for debugging
            logger.error(f"Unexpected error during artifact cleaning: {e}", exc_info=True)
            errors.append(
                f"Unexpected error cleaning artifacts: {type(e).__name__}: {e}\n"
                f"Compiled extensions may not have been cleaned. Try manually deleting .so/.pyd files."
            )

    # Print results
    if cleaned:
        print("🧹 Cleaned:")
        for item in cleaned:
            print(f"   ✓ {item}")
    else:
        print("✨ Nothing to clean")

    if errors:
        print("\n⚠️ Errors:")
        for error in errors:
            print(f"   {error}")


def run_watch(args: argparse.Namespace) -> None:
    """Watch for file changes and recompile automatically.

    Args:
        args: Parsed command-line arguments
    """
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer

    config_overrides = build_config_overrides(args)

    # Load and resolve configuration
    resolver = ConfigResolver(cli_overrides=config_overrides)
    config = resolver.resolve()

    watch_dir = Path(config["nim_source"])

    if not watch_dir.exists():
        sys.exit(f"❌ Nim source directory not found: {watch_dir}")

    build_type = "release" if args.release else "debug"

    # Debounce timer to avoid multiple compilations
    last_compile: float = 0.0
    debounce_delay = DEFAULT_DEBOUNCE_DELAY

    class NimFileHandler(FileSystemEventHandler):
        """Handle Nim file modification events."""

        def on_modified(self, event):
            nonlocal last_compile

            # Only process .nim files
            if not event.src_path.endswith(".nim"):
                return

            # Debounce: wait for file changes to settle
            now = time.time()
            if now - last_compile < debounce_delay:
                return

            last_compile = now

            # Get relative path for cleaner output
            rel_path = Path(event.src_path).relative_to(Path.cwd())
            print(f"\n📝 {rel_path} modified")

            try:
                out = _compile_nim(
                    build_type=build_type,
                    inplace=True,
                    config_overrides=config_overrides,
                )
                print(f"✅ Built {out.name}")

                if args.run_tests:
                    print("🧪 Running tests...")
                    import subprocess

                    result = subprocess.run(["pytest", "-v"], capture_output=False)
                    if result.returncode == 0:
                        print("✅ Tests passed!")
                    else:
                        print("❌ Tests failed")

            except Exception as e:
                # Format error consistently but continue watching
                error_msg = format_error(e)
                if error_msg:
                    print(error_msg)
                else:
                    # CalledProcessError already formatted by backend
                    pass
                logger.debug(f"Compilation error in watch mode: {e}")

            print("👀 Watching for changes... (Ctrl+C to stop)")

    # Set up observer
    event_handler = NimFileHandler()
    observer = Observer()
    observer.schedule(event_handler, str(watch_dir), recursive=True)

    # Initial compilation
    print(f"🚀 Starting watch mode for {watch_dir}/")
    print("👀 Watching for changes... (Ctrl+C to stop)")

    try:
        observer.start()

        # Do initial compile
        try:
            out = _compile_nim(
                build_type=build_type,
                inplace=True,
                config_overrides=config_overrides,
            )
            print(f"✅ Initial build complete: {out.name}")
        except Exception as e:
            # Use consistent error formatting
            error_msg = format_error(e)
            if error_msg:
                print(error_msg)
            logger.warning(f"Initial build failed in watch mode: {e}")

        print("👀 Watching for changes... (Ctrl+C to stop)")

        # Keep running until interrupted
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n👋 Stopping watch mode...")
        observer.stop()
    finally:
        observer.join()


def run_init(args: argparse.Namespace) -> None:
    """Initialize Nuwa in an existing project.

    Args:
        args: Parsed command-line arguments
    """
    path = Path(args.path or ".")

    # 1. Determine Project Name
    project_name = "my_project"
    pyproject_path = path / "pyproject.toml"

    # We read the content once
    content = ""
    if pyproject_path.exists():
        content = pyproject_path.read_text(encoding="utf-8")
        try:
            # Parse to find name safely
            data = tomllib.loads(content)
            project_name = data.get("project", {}).get("name", project_name)
        except Exception:
            # Fallback if file is currently invalid TOML
            project_name = path.resolve().name
    else:
        project_name = path.resolve().name

    # Normalize names
    module_name = normalize_package_name(project_name)
    lib_name = f"{module_name}_lib"

    print(f"✨ Initializing Nuwa for project: {project_name}")

    # 2. Handle pyproject.toml injection
    if pyproject_path.exists():
        try:
            current_config = tomllib.loads(content)
        except Exception:
            print("❌ Error: Existing pyproject.toml is invalid. Cannot modify safely.")
            return

        # CHECK 1: Build System
        # We only append if [build-system] is COMPLETELY missing
        if "build-system" in current_config:
            backend = current_config["build-system"].get("build-backend", "legacy")
            if backend != "nuwa_build":
                print(f"⚠️  Warning: Project uses another build backend ('{backend}').")
                print("   To use Nuwa, you must manually edit pyproject.toml:")
                print("   [build-system]")
                print('   requires = ["nuwa-build"]')
                print('   build-backend = "nuwa_build"')
            else:
                print("✅ Build backend already configured.")
        else:
            print("➕ Adding [build-system] to pyproject.toml")
            with open(pyproject_path, "a", encoding="utf-8") as f:
                f.write(BUILD_SYSTEM_SECTION)

        # CHECK 2: Tool Config
        # We only append if [tool.nuwa] is COMPLETELY missing
        if "tool" in current_config and "nuwa" in current_config["tool"]:
            print("ℹ️  [tool.nuwa] configuration already exists.")
        else:
            print("➕ Adding [tool.nuwa] config to pyproject.toml")
            with open(pyproject_path, "a", encoding="utf-8") as f:
                f.write(TOOL_NUWA_SECTION.format(module_name=module_name))

    else:
        # Create fresh pyproject.toml
        print("📄 Creating pyproject.toml")
        with open(pyproject_path, "w", encoding="utf-8") as f:
            f.write(f'[project]\nname = "{project_name}"\nversion = "0.1.0"\n')
            f.write(BUILD_SYSTEM_SECTION)
            f.write(TOOL_NUWA_SECTION.format(module_name=module_name))

    # 3. Create Nim Directory (Non-destructive)
    nim_dir = path / "nim"
    if not nim_dir.exists():
        print("Pg  Creating nim/ directory")
        nim_dir.mkdir(exist_ok=True)

        # Entry point
        entry_file = nim_dir / f"{lib_name}.nim"
        if not entry_file.exists():
            print(f"Pg  Creating nim/{entry_file.name}")
            with open(entry_file, "w", encoding="utf-8") as f:
                f.write(LIB_NIM.format(module_name=module_name))

        # Helpers
        helpers_file = nim_dir / "helpers.nim"
        if not helpers_file.exists():
            print("Pg  Creating nim/helpers.nim")
            with open(helpers_file, "w", encoding="utf-8") as f:
                f.write(HELPERS_NIM.format(module_name=module_name))
    else:
        print("ℹ️  nim/ directory already exists. Skipping Nim scaffolding.")

    # 4. Gitignore (Append if exists)
    gitignore_path = path / ".gitignore"
    if gitignore_path.exists():
        git_content = gitignore_path.read_text(encoding="utf-8")
        if "*.so" not in git_content and "*.pyd" not in git_content:
            print("➕ Adding build artifacts to .gitignore")
            with open(gitignore_path, "a", encoding="utf-8") as f:
                f.write("\n# Nuwa Build Artifacts\n*.so\n*.pyd\nnimcache/\n.nimble/\ndist/\n")
    else:
        print("Pg  Creating .gitignore")
        with open(gitignore_path, "w", encoding="utf-8") as f:
            f.write(GITIGNORE)

    print("\n✅ Initialization complete!")
    print("   Run 'nuwa develop' to compile your first extension")


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(prog="nuwa", description="Build Python extensions with Nim.")

    # Add --version flag
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", required=False)

    # new command
    cmd_new = subparsers.add_parser("new", help="Create a new project")
    cmd_new.add_argument("path", help="Project directory path")
    cmd_new.add_argument("--name", help="Project name (defaults to directory name)")

    # init command
    cmd_init = subparsers.add_parser("init", help="Initialize Nuwa in an existing project")
    cmd_init.add_argument(
        "path", nargs="?", help="Project directory path (defaults to current directory)"
    )

    # develop command
    cmd_dev = subparsers.add_parser("develop", help="Compile in-place")
    cmd_dev.add_argument("-r", "--release", action="store_true", help="Build in release mode")
    cmd_dev.add_argument("--module-name", help="Override Python module name")
    cmd_dev.add_argument("--nim-source", help="Override Nim source directory")
    cmd_dev.add_argument("--entry-point", help="Override entry point file name")
    cmd_dev.add_argument("--output-dir", help="Override output directory")
    cmd_dev.add_argument(
        "--nim-flag",
        action="append",
        dest="nim_flags",
        help="Additional Nim compiler flags (can be used multiple times)",
    )

    # clean command
    cmd_clean = subparsers.add_parser("clean", help="Clean build artifacts and dependencies")
    cmd_clean.add_argument("--deps", action="store_true", help="Only clean .nimble/ dependencies")
    cmd_clean.add_argument(
        "--artifacts", action="store_true", help="Only clean build artifacts and cache"
    )

    # watch command
    cmd_watch = subparsers.add_parser("watch", help="Watch for changes and recompile")
    cmd_watch.add_argument("-r", "--release", action="store_true", help="Build in release mode")
    cmd_watch.add_argument("--module-name", help="Override Python module name")
    cmd_watch.add_argument("--nim-source", help="Override Nim source directory")
    cmd_watch.add_argument("--entry-point", help="Override entry point file name")
    cmd_watch.add_argument("--output-dir", help="Override output directory")
    cmd_watch.add_argument(
        "--nim-flag",
        action="append",
        dest="nim_flags",
        help="Additional Nim compiler flags (can be used multiple times)",
    )
    cmd_watch.add_argument(
        "-t",
        "--run-tests",
        action="store_true",
        help="Run pytest after each successful compilation",
    )

    # build command
    cmd_build = subparsers.add_parser("build", help="Build a wheel package")
    cmd_build.add_argument("-r", "--release", action="store_true", help="Build in release mode")
    cmd_build.add_argument("--module-name", help="Override Python module name")
    cmd_build.add_argument("--nim-source", help="Override Nim source directory")
    cmd_build.add_argument("--entry-point", help="Override entry point file name")
    cmd_build.add_argument("--output-dir", help="Override output directory")
    cmd_build.add_argument(
        "--nim-flag",
        action="append",
        dest="nim_flags",
        help="Additional Nim compiler flags (can be used multiple times)",
    )

    args = parser.parse_args()

    # If no command is provided, show help
    if not args.command:
        parser.print_help()
        sys.exit(0)

    try:
        if args.command == "new":
            run_new(args)
        elif args.command == "init":
            run_init(args)
        elif args.command == "develop":
            run_develop(args)
        elif args.command == "build":
            run_build(args)
        elif args.command == "clean":
            run_clean(args)
        elif args.command == "watch":
            run_watch(args)
    except Exception as e:
        # Handle any uncaught exceptions with consistent formatting
        handle_cli_error(e, context=f"Error in command '{args.command}'")


if __name__ == "__main__":
    main()
