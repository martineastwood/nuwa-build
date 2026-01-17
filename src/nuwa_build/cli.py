"""Command-line interface for Nuwa Build."""

__version__ = "0.2.5"

import argparse
import subprocess
import sys
import time
from pathlib import Path

from .backend import _compile_nim
from .templates import (
    EXAMPLE_PY,
    GITHUB_ACTIONS_PUBLISH_YML,
    GITIGNORE,
    HELPERS_NIM,
    INIT_PY,
    LIB_NIM,
    PYPROJECT_TOML,
    README_MD,
    TEST_PY,
)


def run_new(args: argparse.Namespace) -> None:
    """Create a new Nuwa project.

    Args:
        args: Parsed command-line arguments
    """
    path = Path(args.path)
    name = args.name if args.name else path.name
    module_name = name.replace("-", "_")  # Python import safety
    lib_name = f"{module_name}_lib"  # Compiled extension module name

    if path.exists() and any(path.iterdir()):
        sys.exit(f"❌ Error: Directory '{path}' is not empty.")

    print(f"✨ Creating new Nuwa project: {name}")

    try:
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

    except OSError as e:
        sys.exit(f"❌ Error creating project: {e}")


def run_develop(args: argparse.Namespace) -> None:
    """Compile the project in-place.

    Args:
        args: Parsed command-line arguments
    """
    build_type = "release" if args.release else "debug"

    # Build config overrides from CLI args
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

    try:
        _compile_nim(
            build_type=build_type,
            inplace=True,
            config_overrides=config_overrides if config_overrides else None,
        )
        # Note: Success message is printed by backend.py
        print("💡 Module updated. Run your tests or scripts to verify.")
    except FileNotFoundError as e:
        sys.exit(f"❌ Error: {e}")
    except ValueError as e:
        sys.exit(f"❌ Configuration Error: {e}")
    except subprocess.CalledProcessError:
        # Error already formatted and printed by backend.py
        sys.exit(1)
    except Exception as e:
        sys.exit(f"❌ Error: {e}")


def run_build(args: argparse.Namespace) -> None:
    """Build a wheel package.

    Args:
        args: Parsed command-line arguments
    """
    from .backend import build_wheel

    # Build config overrides from CLI args (same pattern as run_develop)
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

    # Setup output directory
    dist_dir = Path.cwd() / "dist"

    try:
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

    except FileNotFoundError as e:
        sys.exit(f"❌ Error: {e}")
    except ValueError as e:
        sys.exit(f"❌ Configuration Error: {e}")
    except subprocess.CalledProcessError:
        # Error already formatted and printed by backend.py
        sys.exit(1)
    except Exception as e:
        sys.exit(f"❌ Error: {e}")


def run_clean(args: argparse.Namespace) -> None:
    """Clean build artifacts and dependencies.

    Args:
        args: Parsed command-line arguments
    """
    import shutil

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
            from .config import parse_nuwa_config

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

        except Exception as e:
            # If config loading fails, skip artifact cleaning to be safe
            errors.append(f"Could not load config for artifact cleaning: {e}")

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

    # Build config overrides from CLI args
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

    # Load configuration to get nim source directory
    from .config import parse_nuwa_config

    config = parse_nuwa_config()
    if config_overrides:
        from .config import merge_cli_args

        config = merge_cli_args(config, config_overrides)

    watch_dir = Path(config["nim_source"])

    if not watch_dir.exists():
        sys.exit(f"❌ Nim source directory not found: {watch_dir}")

    build_type = "release" if args.release else "debug"

    # Debounce timer to avoid multiple compilations
    last_compile: float = 0.0
    debounce_delay = 0.5  # seconds

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
                    config_overrides=config_overrides if config_overrides else None,
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

            except FileNotFoundError as e:
                print(f"❌ Error: {e}")
            except ValueError as e:
                print(f"❌ Configuration Error: {e}")
            except Exception as e:
                print(f"❌ Compilation failed: {e}")

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
                config_overrides=config_overrides if config_overrides else None,
            )
            print(f"✅ Initial build complete: {out.name}")
        except Exception as e:
            print(f"❌ Initial build failed: {e}")

        print("👀 Watching for changes... (Ctrl+C to stop)")

        # Keep running until interrupted
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n👋 Stopping watch mode...")
        observer.stop()
    finally:
        observer.join()


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(prog="nuwa", description="Build Python extensions with Nim.")

    # Add --version flag
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", required=False)

    # new command
    cmd_new = subparsers.add_parser("new", help="Create a new project")
    cmd_new.add_argument("path", help="Project directory path")
    cmd_new.add_argument("--name", help="Project name (defaults to directory name)")

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

    if args.command == "new":
        run_new(args)
    elif args.command == "develop":
        run_develop(args)
    elif args.command == "build":
        run_build(args)
    elif args.command == "clean":
        run_clean(args)
    elif args.command == "watch":
        run_watch(args)


if __name__ == "__main__":
    main()
