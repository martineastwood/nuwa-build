"""File watching functionality for Nuwa Build."""

import logging
import subprocess
import time
from pathlib import Path
from typing import Optional

from .backend import _compile_nim
from .config import ConfigResolver
from .constants import DEFAULT_DEBOUNCE_DELAY
from .errors import format_error

logger = logging.getLogger("nuwa")


class NimFileHandler:
    """Handle Nim file modification events for watch mode."""

    def __init__(
        self,
        build_type: str,
        config_overrides: Optional[dict],
        run_tests: bool,
        debounce_delay: float,
    ):
        """Initialize the file handler.

        Args:
            build_type: "debug" or "release"
            config_overrides: Optional config overrides
            run_tests: Whether to run tests after compilation
            debounce_delay: Delay in seconds between compilations
        """
        from watchdog.events import FileSystemEventHandler

        self.build_type = build_type
        self.config_overrides = config_overrides
        self.run_tests = run_tests
        self.debounce_delay = debounce_delay
        self.last_compile: float = 0.0

        # Create a proxy handler to avoid mypy "Cannot assign to a method" error
        class _ProxyHandler(FileSystemEventHandler):
            def on_modified(_, event):
                self.on_modified(event)

        self.handler = _ProxyHandler()

    def on_modified(self, event) -> None:
        """Handle file modification events.

        Args:
            event: Watchdog file system event
        """
        # Only process .nim files
        if not event.src_path.endswith(".nim"):
            return

        # Debounce: wait for file changes to settle
        now = time.time()
        if now - self.last_compile < self.debounce_delay:
            return

        self.last_compile = now

        # Get relative path for cleaner output
        rel_path = Path(event.src_path).relative_to(Path.cwd())
        print(f"\n📝 {rel_path} modified")

        try:
            out = _compile_nim(
                build_type=self.build_type,
                inplace=True,
                config_overrides=self.config_overrides,
            )
            print(f"✅ Built {out.name}")

            if self.run_tests:
                print("🧪 Running tests...")
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


def run_watch(args) -> None:
    """Watch for file changes and recompile automatically.

    Args:
        args: Parsed command-line arguments
    """
    from watchdog.observers import Observer

    # Build config overrides from args
    from .config import build_config_overrides

    config_overrides = build_config_overrides(
        module_name=args.module_name,
        nim_source=args.nim_source,
        entry_point=args.entry_point,
        output_location=args.output_dir,
        nim_flags=args.nim_flags,
    )

    # Load and resolve configuration
    resolver = ConfigResolver(cli_overrides=config_overrides)
    config = resolver.resolve()

    watch_dir = Path(config["nim_source"])

    if not watch_dir.exists():
        raise FileNotFoundError(f"Nim source directory not found: {watch_dir}")

    build_type = "release" if args.release else "debug"
    debounce_delay = DEFAULT_DEBOUNCE_DELAY

    # Set up observer with NimFileHandler
    event_handler = NimFileHandler(
        build_type=build_type,
        config_overrides=config_overrides,
        run_tests=args.run_tests,
        debounce_delay=debounce_delay,
    )
    observer = Observer()
    observer.schedule(event_handler.handler, str(watch_dir), recursive=True)

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
