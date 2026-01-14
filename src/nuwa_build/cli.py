"""Command-line interface for Nuwa Build."""

import argparse
import subprocess
import sys
import time
from pathlib import Path

from .backend import _compile_nim
from .templates import (
    EXAMPLE_PY,
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

        # Write pyproject.toml
        with open(path / "pyproject.toml", "w") as f:
            f.write(PYPROJECT_TOML.format(
                project_name=name,
                module_name=module_name
            ))

        # Write Nim sources - entry point filename determines Python module name
        with open(path / "nim" / f"{lib_name}.nim", "w") as f:
            f.write(LIB_NIM.format(module_name=module_name))

        with open(path / "nim" / "helpers.nim", "w") as f:
            f.write(HELPERS_NIM.format(module_name=module_name))

        # Write Python package with __init__.py
        with open(path / module_name / "__init__.py", "w") as f:
            f.write(INIT_PY.format(module_name=module_name))

        # Write README
        with open(path / "README.md", "w") as f:
            f.write(README_MD.format(
                project_name=name,
                module_name=module_name
            ))

        # Write supporting files
        with open(path / ".gitignore", "w") as f:
            f.write(GITIGNORE)

        with open(path / "example.py", "w") as f:
            f.write(EXAMPLE_PY.format(module_name=module_name))

        # Write test file
        with open(path / "tests" / f"test_{module_name}.py", "w") as f:
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
            config_overrides=config_overrides if config_overrides else None
        )
        # Note: Success message is printed by backend.py
        print("💡 Run 'python example.py' or 'pytest' to test your module")
    except FileNotFoundError as e:
        sys.exit(f"❌ Error: {e}")
    except ValueError as e:
        sys.exit(f"❌ Configuration Error: {e}")
    except subprocess.CalledProcessError:
        # Error already formatted and printed by backend.py
        sys.exit(1)
    except Exception as e:
        sys.exit(f"❌ Error: {e}")


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
    last_compile = 0
    debounce_delay = 0.5  # seconds

    class NimFileHandler(FileSystemEventHandler):
        """Handle Nim file modification events."""

        def on_modified(self, event):
            nonlocal last_compile

            # Only process .nim files
            if not event.src_path.endswith('.nim'):
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
                    config_overrides=config_overrides if config_overrides else None
                )
                print(f"✅ Built {out.name}")

                if args.run_tests:
                    print("🧪 Running tests...")
                    import subprocess
                    result = subprocess.run(
                        ["pytest", "-v"],
                        capture_output=False
                    )
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
                config_overrides=config_overrides if config_overrides else None
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
    parser = argparse.ArgumentParser(
        prog="nuwa",
        description="Build Python extensions with Nim."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # new command
    cmd_new = subparsers.add_parser("new", help="Create a new project")
    cmd_new.add_argument("path", help="Project directory path")
    cmd_new.add_argument("--name", help="Project name (defaults to directory name)")

    # develop command
    cmd_dev = subparsers.add_parser("develop", help="Compile in-place")
    cmd_dev.add_argument(
        "-r", "--release",
        action="store_true",
        help="Build in release mode"
    )
    cmd_dev.add_argument(
        "--module-name",
        help="Override Python module name"
    )
    cmd_dev.add_argument(
        "--nim-source",
        help="Override Nim source directory"
    )
    cmd_dev.add_argument(
        "--entry-point",
        help="Override entry point file name"
    )
    cmd_dev.add_argument(
        "--output-dir",
        help="Override output directory"
    )
    cmd_dev.add_argument(
        "--nim-flag",
        action="append",
        dest="nim_flags",
        help="Additional Nim compiler flags (can be used multiple times)"
    )

    # watch command
    cmd_watch = subparsers.add_parser("watch", help="Watch for changes and recompile")
    cmd_watch.add_argument(
        "-r", "--release",
        action="store_true",
        help="Build in release mode"
    )
    cmd_watch.add_argument(
        "--module-name",
        help="Override Python module name"
    )
    cmd_watch.add_argument(
        "--nim-source",
        help="Override Nim source directory"
    )
    cmd_watch.add_argument(
        "--entry-point",
        help="Override entry point file name"
    )
    cmd_watch.add_argument(
        "--output-dir",
        help="Override output directory"
    )
    cmd_watch.add_argument(
        "--nim-flag",
        action="append",
        dest="nim_flags",
        help="Additional Nim compiler flags (can be used multiple times)"
    )
    cmd_watch.add_argument(
        "-t", "--run-tests",
        action="store_true",
        help="Run pytest after each successful compilation"
    )

    args = parser.parse_args()

    if args.command == "new":
        run_new(args)
    elif args.command == "develop":
        run_develop(args)
    elif args.command == "watch":
        run_watch(args)


if __name__ == "__main__":
    main()
