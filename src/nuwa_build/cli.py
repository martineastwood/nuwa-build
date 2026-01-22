"""Command-line interface for Nuwa Build."""

import argparse
import subprocess
import sys
import traceback
from pathlib import Path

from . import __version__
from .backend import _compile_nim
from .cleanup import clean_all, clean_artifacts, clean_dependencies
from .config import build_config_overrides
from .errors import format_error
from .pep517_hooks import build_wheel
from .scaffolding import (
    create_example_file,
    create_github_actions,
    create_nim_scaffolding,
    create_python_package_scaffolding,
    create_readme,
    create_tests_scaffolding,
    determine_project_name,
    update_gitignore,
    update_pyproject_toml,
)
from .templates import LIB_NIM, PYPROJECT_TOML
from .utils import (
    normalize_package_name,
    validate_module_name,
    validate_path,
    validate_project_name,
)
from .watch import run_watch


def add_build_arguments(parser):
    """Add common build-related arguments to a parser.

    Args:
        parser: ArgumentParser or subparser to add arguments to
    """
    parser.add_argument("--module-name", help="Override Python module name")
    parser.add_argument("--nim-source", help="Override Nim source directory")
    parser.add_argument("--entry-point", help="Override entry point file name")
    parser.add_argument("--output-dir", help="Override output directory")
    parser.add_argument(
        "--nim-flag",
        action="append",
        dest="nim_flags",
        help="Additional Nim compiler flags (can be used multiple times)",
    )


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

        print(f"{context}: {error}")
        traceback.print_exc()

    sys.exit(1)


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
        raise ValueError(f"Directory '{path}' is not empty.")

    print(f"✨ Creating new Nuwa project: {name}")

    # Create directory structure
    (path / "nim").mkdir(parents=True, exist_ok=True)

    # Write pyproject.toml
    (path / "pyproject.toml").write_text(
        PYPROJECT_TOML.format(project_name=name, module_name=module_name)
    )

    # Write Nim sources - entry point filename determines Python module name
    (path / "nim" / f"{lib_name}.nim").write_text(LIB_NIM.format(module_name=module_name))

    # Use scaffolding module for common tasks

    create_nim_scaffolding(path, module_name, lib_name)  # Creates helpers.nim
    create_python_package_scaffolding(path, module_name)
    create_tests_scaffolding(path, module_name)
    create_example_file(path, module_name)
    create_readme(path, name, module_name)
    create_github_actions(path)
    update_gitignore(path)

    print(f"✅ Ready! \n   cd {path}\n   nuwa develop\n   python example.py\n   pytest")


def run_develop(args: argparse.Namespace) -> None:
    """Compile the project in-place.

    Args:
        args: Parsed command-line arguments
    """
    build_type = "release" if args.release else "debug"
    config_overrides = build_config_overrides(
        module_name=args.module_name,
        nim_source=args.nim_source,
        entry_point=args.entry_point,
        output_location=args.output_dir,
        nim_flags=args.nim_flags,
    )

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
    config_overrides = build_config_overrides(
        module_name=args.module_name,
        nim_source=args.nim_source,
        entry_point=args.entry_point,
        output_location=args.output_dir,
        nim_flags=args.nim_flags,
    )

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
    # Determine what to clean based on flags
    clean_all_flag = not (args.deps or args.artifacts)

    # Perform the requested cleanup
    if clean_all_flag:
        cleaned, errors = clean_all()
    elif args.deps:
        cleaned, errors = clean_dependencies()
    else:  # args.artifacts
        cleaned, errors = clean_artifacts()

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


def run_init(args: argparse.Namespace) -> None:
    """Initialize Nuwa in an existing project.

    Args:
        args: Parsed command-line arguments
    """
    path = Path(args.path or ".")
    pyproject_path = path / "pyproject.toml"

    # 1. Determine Project Name
    project_name = determine_project_name(path, pyproject_path)

    # Normalize names
    module_name = normalize_package_name(project_name)
    lib_name = f"{module_name}_lib"

    print(f"✨ Initializing Nuwa for project: {project_name}")

    # 2. Handle pyproject.toml injection
    update_pyproject_toml(pyproject_path, module_name, project_name)

    # 3. Create Nim Directory (Non-destructive)

    create_nim_scaffolding(path, module_name, lib_name)

    # 4. Gitignore (Append if exists)
    update_gitignore(path)

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
    add_build_arguments(cmd_dev)

    # clean command
    cmd_clean = subparsers.add_parser("clean", help="Clean build artifacts and dependencies")
    cmd_clean.add_argument("--deps", action="store_true", help="Only clean .nimble/ dependencies")
    cmd_clean.add_argument(
        "--artifacts", action="store_true", help="Only clean build artifacts and cache"
    )

    # watch command
    cmd_watch = subparsers.add_parser("watch", help="Watch for changes and recompile")
    cmd_watch.add_argument("-r", "--release", action="store_true", help="Build in release mode")
    add_build_arguments(cmd_watch)
    cmd_watch.add_argument(
        "-t",
        "--run-tests",
        action="store_true",
        help="Run pytest after each successful compilation",
    )

    # build command
    cmd_build = subparsers.add_parser("build", help="Build a wheel package")
    cmd_build.add_argument("-r", "--release", action="store_true", help="Build in release mode")
    add_build_arguments(cmd_build)

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
