"""Utility functions for Nuwa Build."""

import os
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from packaging.tags import sys_tags


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

    Returns:
        ".pyd" for Windows, ".so" for other platforms.
    """
    return ".pyd" if sys.platform == "win32" else ".so"


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

    Yields:
        Path to temporary directory

    Example:
        with temp_directory() as temp_dir:
            # Do work with temp_dir
            pass
        # Directory is automatically cleaned up
    """
    temp_dir = Path(tempfile.mkdtemp())
    try:
        yield temp_dir
    finally:
        # Clean up directory
        if temp_dir.exists():
            shutil.rmtree(temp_dir)


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


def install_nimble_dependencies(deps: list, local_dir: Optional[Path] = None) -> None:
    """Install missing nimble dependencies.

    Args:
        deps: List of nimble package names or specs (e.g., ["nimpy", "cligen >= 1.0.0"])
        local_dir: Optional path to local nimble directory (for project-level isolation)

    Raises:
        RuntimeError: If nimble is not installed or installation fails.
    """
    if not deps:
        return

    if not check_nimble_installed():
        raise RuntimeError(
            "nimble package manager not found in PATH.\n"
            "Nimble is installed with Nim. Make sure Nim is properly installed.\n"
            "Visit https://nim-lang.org/install.html for instructions."
        )

    # When using a local directory, we skip the "already installed" check
    # since checking against a custom nimbleDir is complex.
    # We rely on nimble's internal caching to skip re-installation if already present.
    deps_to_install = deps

    if local_dir:
        # Enforce project-level isolation
        local_dir_abs = local_dir.resolve()
        # Create the directory if it doesn't exist
        local_dir_abs.mkdir(parents=True, exist_ok=True)
        print(f"📦 Installing dependencies to {local_dir}...")
    else:
        # Get list of installed packages for global installs
        try:
            result = subprocess.run(
                ["nimble", "list", "-i"], capture_output=True, text=True, check=False
            )
            installed = result.stdout.lower()
        except (FileNotFoundError, PermissionError, subprocess.SubprocessError):
            installed = ""

        # Extract package names from dependency specs (remove version constraints)
        deps_to_install = []
        for dep in deps:
            # Extract package name (first word, before version specs)
            pkg_name = dep.split()[0].lower()
            if pkg_name not in installed:
                deps_to_install.append(dep)

        # Skip if all dependencies are already installed
        if not deps_to_install:
            return

        print(f"📦 Installing nimble dependencies globally: {', '.join(deps_to_install)}")

    # Build base install command
    install_args = ["nimble", "install", "-y"]
    if local_dir:
        # Set environment variable to override nimble directory
        env = os.environ.copy()
        env["NIMBLE_DIR"] = str(local_dir)

    # Try to install each dependency
    for dep in deps_to_install:
        print(f"  Installing {dep}...")
        try:
            cmd = install_args + [dep]
            if local_dir:
                result = subprocess.run(cmd, capture_output=True, text=True, check=False, env=env)
            else:
                result = subprocess.run(cmd, capture_output=True, text=True, check=False)

            if result.returncode != 0:
                # Check if it's already installed (nimble returns non-zero if already installed)
                if (
                    "already installed" in result.stdout.lower()
                    or "already installed" in result.stderr.lower()
                ):
                    print(f"    ✓ {dep} already installed")
                else:
                    print(f"    ⚠ Failed to install {dep}")
                    print(f"    Output: {result.stdout}")
                    if result.stderr:
                        print(f"    Errors: {result.stderr}")
                    # Don't fail hard, just warn
            else:
                print(f"    ✓ {dep} installed successfully")

        except FileNotFoundError:
            raise RuntimeError(
                "nimble command not found. Make sure Nim is properly installed and in your PATH."
            ) from None
        except (OSError, subprocess.SubprocessError) as e:
            print(f"    ⚠ Error installing {dep}: {e}")
            # Don't fail hard, just warn and continue

    print("✓ Nimble dependencies ready")
