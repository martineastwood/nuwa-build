"""IPython magic commands for compiling Nim code in Jupyter notebooks."""

# mypy: disable-error-code="unused-ignore"

import hashlib
import importlib.util
import logging
import shutil
import sys
from pathlib import Path
from typing import Optional

from IPython import get_ipython  # type: ignore[import-not-found]
from IPython.core.magic import (  # type: ignore[import-not-found]
    Magics,
    cell_magic,
    line_magic,
    magics_class,
)

from .backend import _build_nim_command, _generate_type_stubs, _run_compilation
from .utils import check_nim_installed, get_platform_extension

logger = logging.getLogger("nuwa")


@magics_class
class NuwaMagics(Magics):
    """IPython magic commands for Nuwa Build."""

    CACHE_DIR = Path(".nuwacache")

    def __init__(self, shell):
        """Initialize the magic.

        Args:
            shell: IPython shell instance
        """
        super().__init__(shell)
        self._ensure_cache_dir()

    def _ensure_cache_dir(self):
        """Create .nuwacache directory if it doesn't exist."""
        self.CACHE_DIR.mkdir(exist_ok=True)
        logger.debug(f"Cache directory: {self.CACHE_DIR.absolute()}")

    def _compute_hash(self, code: str, flags: list[str]) -> str:
        """Compute hash of code + flags for cache key.

        Args:
            code: Nim source code
            flags: Compiler flags

        Returns:
            SHA-256 hash as hexadecimal string
        """
        # Sort flags for consistent hashing
        content = code + "".join(sorted(flags))
        return hashlib.sha256(content.encode()).hexdigest()

    def _parse_magic_line(self, line: str) -> list[str]:
        """Parse compiler flags from magic line.

        Args:
            line: The line argument from %%nuwa (e.g., "-d:release --opt:speed")

        Returns:
            List of compiler flags
        """
        if not line.strip():
            return []
        return line.strip().split()

    def _find_cached_extension(self, cache_path: Path, module_name: str) -> Optional[Path]:
        """Find compiled .so/.pyd in cache directory.

        Args:
            cache_path: Path to cache directory
            module_name: Name of the module

        Returns:
            Path to compiled extension, or None if not found
        """
        ext = get_platform_extension()
        so_name = f"{module_name}_lib{ext}"
        so_path = cache_path / module_name / so_name

        if so_path.exists():
            logger.debug(f"Found cached extension: {so_path}")
            return so_path

        logger.debug(f"No cached extension found at: {so_path}")
        return None

    def _generate_minimal_pyproject(self, module_name: str, cache_dir: Path) -> Path:
        """Generate minimal pyproject.toml for Jupyter compilation.

        Args:
            module_name: Name of the module
            cache_dir: Cache directory path

        Returns:
            Path to generated pyproject.toml
        """
        config = f"""[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "{module_name}"
version = "0.1.0"

[tool.nuwa]
nim-source = "nim"
module-name = "{module_name}"
lib-name = "{module_name}_lib"
entry-point = "{module_name}_lib.nim"
"""
        pyproject_path = cache_dir / "pyproject.toml"
        cache_dir.mkdir(parents=True, exist_ok=True)
        pyproject_path.write_text(config)
        logger.debug(f"Generated pyproject.toml at: {pyproject_path}")
        return pyproject_path

    def _compile_nim_from_string(
        self,
        _nim_code: str,
        module_name: str,
        cache_dir: Path,
        nim_flags: Optional[list[str]] = None,
    ) -> Path:
        """Compile Nim code from string using cache directory.

        This adapts the existing _compile_nim() workflow:
        1. Reuses check_nim_installed(), get_platform_extension()
        2. Reuses _build_nim_command() for compiler invocation
        3. Reuses _run_compilation() for subprocess execution
        4. Reuses _generate_type_stubs() for .pyi generation

        Args:
            nim_code: Nim source code as string
            module_name: Python module name
            cache_dir: Cache directory path
            nim_flags: Additional compiler flags

        Returns:
            Path to compiled .so/.pyd file

        Raises:
            RuntimeError: If Nim compiler not found
            subprocess.CalledProcessError: If compilation fails
        """
        # Check Nim is available
        check_nim_installed()

        # Determine paths
        nim_dir = cache_dir / "nim"
        entry_point = nim_dir / f"{module_name}_lib.nim"
        ext = get_platform_extension()
        output_path = cache_dir / module_name / f"{module_name}_lib{ext}"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Build command (release build by default)
        cmd = _build_nim_command(
            entry_point=entry_point,
            output_path=output_path,
            build_type="release",
            nim_flags=nim_flags or [],
            nim_dir=nim_dir,
            nimble_path=None,  # No nimble deps for Jupyter
        )

        # Run compilation
        result = _run_compilation(cmd, entry_point, output_path)

        # Generate type stubs
        lib_name = f"{module_name}_lib"
        _generate_type_stubs(lib_name, result.stdout, output_path.parent)

        return output_path

    def _extract_exported_functions(self, module) -> dict:
        """Extract functions exported via {.exportpy.} pragma.

        Args:
            module: Compiled Python module

        Returns:
            Dictionary of function name -> function object
        """
        functions = {}
        for name in dir(module):
            if name.startswith("_"):
                continue
            obj = getattr(module, name)
            if callable(obj):
                functions[name] = obj
        return functions

    def _inject_compiled_module(self, so_path: Path, module_name: str) -> dict:
        """Load compiled extension and inject functions into IPython namespace.

        Args:
            so_path: Path to compiled .so/.pyd file
            module_name: Python module name

        Returns:
            Dictionary of injected function names
        """
        # Add module directory to sys.path
        module_dir = so_path.parent
        if str(module_dir) not in sys.path:
            sys.path.insert(0, str(module_dir))
            logger.debug(f"Added {module_dir} to sys.path")

        # Import the compiled module
        lib_name = f"{module_name}_lib"
        spec = importlib.util.spec_from_file_location(lib_name, so_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Failed to load module spec for {lib_name} from {so_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Extract exported functions
        functions = self._extract_exported_functions(module)

        # Inject into IPython namespace
        shell = get_ipython()
        for name, func in functions.items():
            shell.user_ns[name] = func

        logger.debug(f"Injected {len(functions)} functions into namespace")
        return functions

    def _format_jupyter_error(self, error: str, cache_dir: Path) -> None:
        """Format compilation errors for Jupyter display.

        Args:
            error: Error message
            cache_dir: Cache directory path
        """
        print(f"❌ Compilation failed:\n{error}")
        print(f"\n💡 Debug files in: {cache_dir.absolute()}")
        print("🧹 Clear cache with: %nuwa_cleanup")

    @cell_magic
    def nuwa(self, line, cell):
        """Compile Nim code and inject functions into namespace.

        Usage:
            %%nuwa [-d:release] [--opt:speed]
            proc add(a, b: int): int {.exportpy.} =
              return a + b

        Args:
            line: Compiler flags (e.g., "-d:release --opt:speed")
            cell: Nim source code
        """
        # 1. Parse compiler flags from line
        nim_flags = self._parse_magic_line(line)

        # 2. Compute hash of code + flags for caching
        code_hash = self._compute_hash(cell, nim_flags)
        module_name = f"nuwa_{code_hash[:12]}"  # 12 chars is plenty for uniqueness

        # 3. Check if already compiled (cache hit)
        cache_path = self.CACHE_DIR / module_name
        if cache_path.exists():
            print(f"🔄 Using cached compilation: {module_name}")
            so_path = self._find_cached_extension(cache_path, module_name)
            if so_path:
                try:
                    injected = self._inject_compiled_module(so_path, module_name)
                    print(
                        f"✅ Loaded {len(injected)} functions from cache: {', '.join(injected.keys())}"
                    )
                    return
                except Exception as e:
                    logger.warning(f"Failed to load cached module: {e}. Recompiling...")
                    # Fall through to recompile

        # 4. Cache miss - compile new code
        print(f"🔨 Compiling: {module_name}")

        # 5. Generate minimal pyproject.toml
        self._generate_minimal_pyproject(module_name, cache_path)

        # 6. Write Nim code to cache
        nim_dir = cache_path / "nim"
        nim_dir.mkdir(exist_ok=True)
        entry_point = nim_dir / f"{module_name}_lib.nim"

        # Automatically add import nuwa_sdk if not present (required for {.nuwa_export.})
        nim_code = cell
        if "import nuwa_sdk" not in nim_code and "nuwa_export" in nim_code:
            nim_code = "import nuwa_sdk\n\n" + nim_code
            logger.debug("Auto-added 'import nuwa_sdk' for {.nuwa_export.} pragma")

        entry_point.write_text(nim_code)
        logger.debug(f"Wrote Nim code to: {entry_point}")

        # 7. Compile using adapted _compile_nim logic
        try:
            so_path = self._compile_nim_from_string(
                cell,
                module_name=module_name,
                cache_dir=cache_path,
                nim_flags=nim_flags,
            )
        except Exception as e:
            self._format_jupyter_error(str(e), cache_path)
            return

        # 8. Load and inject into namespace
        try:
            injected = self._inject_compiled_module(
                so_path=so_path,
                module_name=module_name,
            )
        except Exception as e:
            print(f"❌ Failed to load compiled module: {e}")
            return

        # 9. Show success message with injected functions
        print(
            f"✅ Compiled {module_name} and injected {len(injected)} functions: {', '.join(injected.keys())}"
        )

    @line_magic
    def nuwa_cleanup(self, _line):
        """Clear the .nuwacache directory.

        Usage:
            %nuwa_cleanup
        """
        if self.CACHE_DIR.exists():
            shutil.rmtree(self.CACHE_DIR)
            print(f"🧹 Cleared cache: {self.CACHE_DIR.absolute()}")
        else:
            print(f"✅ Cache already clean: {self.CACHE_DIR.absolute()}")
        self._ensure_cache_dir()  # Recreate for future use

    @line_magic
    def nuwa_cache_info(self, _line):
        """Show cache statistics.

        Usage:
            %nuwa_cache_info
        """
        if not self.CACHE_DIR.exists():
            print("📊 Cache: empty")
            return

        modules = [d for d in self.CACHE_DIR.iterdir() if d.is_dir()]
        total_size = sum(f.stat().st_size for d in modules for f in d.rglob("*") if f.is_file())

        print(f"📊 Cache: {len(modules)} modules, {total_size / 1024:.1f} KB")
        print(f"📍 Location: {self.CACHE_DIR.absolute()}")


def load_ipython_extension(ipython):
    """Load the Nuwa magic extension.

    Called by IPython when user runs: %load_ext nuwa_build.magic

    Args:
        ipython: IPython shell instance
    """
    ipython.register_magics(NuwaMagics)
    logger.info("Registered Nuwa magic commands")
