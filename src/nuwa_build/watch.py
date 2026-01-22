"""File watching functionality for Nuwa Build."""

import subprocess
import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from .backend import _compile_nim
from .config import build_config_overrides, merge_cli_args, parse_nuwa_config
from .errors import format_error
from .utils import DEFAULT_DEBOUNCE_DELAY


def run_watch(args) -> None:
    """Watch for file changes and recompile automatically.

    Args:
        args: Parsed command-line arguments
    """

    # Get profile from args (may be None)
    profile = getattr(args, "profile", None)

    # Build config overrides from args
    config_overrides = build_config_overrides(
        module_name=args.module_name,
        nim_source=args.nim_source,
        entry_point=args.entry_point,
        output_location=args.output_dir,
        nim_flags=args.nim_flags,
        profile=profile,
    )

    # Load and resolve configuration
    # Determine build type - profile takes precedence over --release flag
    if profile:
        build_type = "release" if profile == "release" else "debug"
    else:
        build_type = "release" if args.release else "debug"

    config = parse_nuwa_config(profile=profile)
    if config_overrides:
        config = merge_cli_args(config, config_overrides)

    watch_dir = Path(config["nim_source"])

    if not watch_dir.exists():
        raise FileNotFoundError(f"Nim source directory not found: {watch_dir}")

    debounce_delay = DEFAULT_DEBOUNCE_DELAY

    # Create handler with closure for state
    last_compile = [0.0]  # Use list for mutability in closure

    def on_modified(event) -> None:
        """Handle file modification events."""
        # Only process .nim files
        if not event.src_path.endswith(".nim"):
            return

        # Debounce: wait for file changes to settle
        now = time.time()
        if now - last_compile[0] < debounce_delay:
            return

        last_compile[0] = now

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
                result = subprocess.run(["pytest", "-v"], capture_output=False)
                if result.returncode == 0:
                    print("✅ Tests passed!")
                else:
                    print("❌ Tests failed")

        except Exception as e:
            # Print error and continue watching (watch mode is resilient)
            # CalledProcessError is already formatted by backend
            if not isinstance(e, subprocess.CalledProcessError):
                error_msg = format_error(e)
                if error_msg:
                    print(error_msg)

        print("👀 Watching for changes... (Ctrl+C to stop)")

    # Create watchdog handler
    class _EventHandler(FileSystemEventHandler):
        def on_modified(self_, event):
            on_modified(event)

    event_handler = _EventHandler()
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
            # Print error and continue watching
            # CalledProcessError is already formatted by backend
            if not isinstance(e, subprocess.CalledProcessError):
                error_msg = format_error(e)
                if error_msg:
                    print(error_msg)

        print("👀 Watching for changes... (Ctrl+C to stop)")

        # Keep running until interrupted
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n👋 Stopping watch mode...")
        observer.stop()
    finally:
        observer.join()
