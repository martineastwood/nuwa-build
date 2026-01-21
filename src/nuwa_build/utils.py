"""Utility functions for Nuwa Build."""

import builtins
import contextlib
import os
import re
import shutil
import subprocess
import sys
import sysconfig
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from packaging.tags import sys_tags

# ====================
# Constants
# ====================

# Compilation constants
NIM_APP_LIB_FLAG = "--app:lib"
RELEASE_FLAG = "-d:release"

# Nimble directory constants
NIMBLE_PKGS_DIR = "pkgs"
NIMBLE_PKGS2_DIR = "pkgs2"

# File extension constants
PYD_EXTENSION = ".pyd"
SO_EXTENSION = ".so"

# Watch mode timing
DEFAULT_DEBOUNCE_DELAY = 0.5  # seconds

# Output location constants
OUTPUT_LOCATION_AUTO = "auto"
OUTPUT_LOCATION_SRC = "src"

# Default configuration values
DEFAULT_NIM_SOURCE_DIR = "nim"
DEFAULT_OUTPUT_LOCATION = "auto"


def normalize_package_name(name: str) -> str:
    """Normalize a package name by replacing hyphens with underscores.

    Per PEP 427, wheel filenames and dist-info directories must use underscores
    even if the package name uses hyphens.

    Args:
        name: Package name that may contain hyphens

    Returns:
        Normalized package name with underscores

    Example:
        >>> normalize_package_name("my-package")
        'my_package'
    """
    return name.replace("-", "_")


def check_nim_installed() -> None:
    """Check if Nim compiler is installed and accessible.

    Raises:
        RuntimeError: If Nim is not found or not working.
    """
    if not shutil.which("nim"):
        raise RuntimeError(
            "Nim compiler not found in PATH.\nInstall Nim from https://nim-lang.org/install.html"
        )

    # Verify nim works
    try:
        subprocess.run(["nim", "--version"], capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"Nim compiler not working:\n{e.stderr}\nCheck your Nim installation."
        ) from e


def get_platform_extension() -> str:
    """Get the platform-specific shared library extension.

    Uses sysconfig to get the exact extension Python expects for the current
    platform, which may include ABI tags (e.g., '.cpython-310-x86_64-linux-gnu.so').

    Returns:
        Platform-specific extension for compiled Python extensions.
    """
    ext_suffix = sysconfig.get_config_var("EXT_SUFFIX")
    if ext_suffix is None:
        # Fallback for older Python versions or unusual builds
        return PYD_EXTENSION if sys.platform == "win32" else SO_EXTENSION
    # Type narrowing: EXT_SUFFIX is always a string when not None
    assert isinstance(ext_suffix, str)
    return ext_suffix


def get_wheel_tags(name: str, version: str) -> str:
    """Generate wheel filename with proper platform tags.

    Uses packaging.tags to correctly determine Python, ABI, and platform tags,
    including support for Python 3.14+ free-threaded builds (cp314t ABI tags).

    Args:
        name: Package name
        version: Package version

    Returns:
        Wheel filename with proper tags
    """
    # Normalize package name: replace hyphens with underscores
    name_normalized = normalize_package_name(name)

    # Get the most specific tag for the current system
    # sys_tags() yields compatible tags in order of specificity (most specific first)
    # This automatically handles:
    # - Python interpreter tags (cp313, cp314, etc.)
    # - Free-threaded ABI tags (cp314t, etc.) for Python 3.14+
    # - Platform-specific tags (macosx, win_amd64, etc.)
    tag = next(sys_tags())

    return f"{name_normalized}-{version}-{tag}.whl"


@contextmanager
def temp_directory():
    """Context manager for a temporary directory.

    Uses tempfile.TemporaryDirectory internally (Python 3.2+).

    Yields:
        Path to temporary directory

    Example:
        with temp_directory() as temp_dir:
            # Do work with temp_dir
            pass
        # Directory is automatically cleaned up
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@contextmanager
def working_directory(path: Path):
    """Context manager for temporarily changing working directory.

    Args:
        path: Directory to change to

    Yields:
        None

    Example:
        with working_directory(Path("/tmp")):
            # Work in /tmp
            pass
        # Automatically return to original directory
    """
    original = Path.cwd()
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(original)


def check_nimble_installed() -> bool:
    """Check if nimble package manager is installed.

    Returns:
        True if nimble is found in PATH, False otherwise.
    """
    return shutil.which("nimble") is not None


def _get_nimble_installed_packages() -> str:
    """Get list of globally installed nimble packages.

    Returns:
        Lowercase string of installed package names, or empty string if check fails.
    """
    try:
        result = subprocess.run(
            ["nimble", "list", "-i"], capture_output=True, text=True, check=False
        )
        return result.stdout.lower()
    except (FileNotFoundError, PermissionError, subprocess.SubprocessError):
        return ""


def _filter_uninstalled_deps(deps: list, installed: str) -> list:
    """Filter out dependencies that are already installed.

    Args:
        deps: List of nimble package specs (e.g., ["nimpy", "cligen >= 1.0.0"])
        installed: Lowercase string of installed package names from `nimble list -i`

    Returns:
        List of deps that need to be installed.
    """
    if not installed:
        # Couldn't check, assume all need installing
        return deps

    deps_to_install = []
    for dep in deps:
        # Extract package name (first word, before version specs)
        pkg_name = dep.split()[0].lower()
        if pkg_name not in installed:
            deps_to_install.append(dep)

    return deps_to_install


def _install_single_nimble_dep(
    dep: str, install_args: list[str], env: Optional[dict] = None
) -> bool:
    """Install a single nimble dependency.

    Args:
        dep: Dependency spec to install
        install_args: Base install command (e.g., ["nimble", "install", "-y"])
        env: Optional environment variables (for local_dir installs)

    Returns:
        True if successfully installed (or already installed), False on failure.
    """
    print(f"  Installing {dep}...")
    try:
        cmd = install_args + [dep]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False, env=env)

        if result.returncode != 0:
            # Check if it's already installed (nimble returns non-zero if already installed)
            if (
                "already installed" in result.stdout.lower()
                or "already installed" in result.stderr.lower()
            ):
                print(f"    ✓ {dep} already installed")
                return True
            else:
                print(f"    ⚠ Failed to install {dep}")
                print(f"    Output: {result.stdout}")
                if result.stderr:
                    print(f"    Errors: {result.stderr}")
                return False
        else:
            print(f"    ✓ {dep} installed successfully")
            return True

    except FileNotFoundError:
        raise RuntimeError(
            "nimble command not found. Make sure Nim is properly installed and in your PATH."
        ) from None
    except (OSError, subprocess.SubprocessError) as e:
        print(f"    ⚠ Error installing {dep}: {e}")
        return False


def install_nimble_dependencies(deps: list, local_dir: Optional[Path] = None) -> None:
    """Install missing nimble dependencies.

    Args:
        deps: List of nimble package names or specs (e.g., ["nimpy", "cligen >= 1.0.0"])
        local_dir: Optional path to local nimble directory (for project-level isolation)

    Raises:
        RuntimeError: If nimble is not installed.
    """
    if not deps:
        return

    if not check_nimble_installed():
        raise RuntimeError(
            "nimble package manager not found in PATH.\n"
            "Nimble is installed with Nim. Make sure Nim is properly installed.\n"
            "Visit https://nim-lang.org/install.html for instructions."
        )

    # Determine which deps need installing
    if local_dir:
        # For local installs, we skip the "already installed" check since
        # checking against a custom nimbleDir is complex. We rely on nimble's
        # internal caching to skip re-installation if already present.
        local_dir.mkdir(parents=True, exist_ok=True)
        deps_to_install = deps
        print(f"📦 Installing dependencies to {local_dir}...")
        env = os.environ.copy()
        env["NIMBLE_DIR"] = str(local_dir)
    else:
        # For global installs, filter out already-installed packages
        installed = _get_nimble_installed_packages()
        deps_to_install = _filter_uninstalled_deps(deps, installed)

        if not deps_to_install:
            return

        print(f"📦 Installing nimble dependencies globally: {', '.join(deps_to_install)}")
        env = None

    # Install each dependency
    install_args = ["nimble", "install", "-y"]
    for dep in deps_to_install:
        _install_single_nimble_dep(dep, install_args, env)

    print("✓ Nimble dependencies ready")


# ====================
# Validation Functions
# ====================


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
    except OSError as e:
        raise ValueError(f"Invalid path '{path}': {e}") from None

    # Check if parent directory exists
    if not resolved.parent.exists():
        raise ValueError(
            f"Parent directory does not exist: {resolved.parent}\n"
            f"Please create the parent directory first."
        )

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
