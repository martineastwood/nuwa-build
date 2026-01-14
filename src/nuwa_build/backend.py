"""Core compilation functionality for Nuwa Build."""

import logging
import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Optional

from .config import load_pyproject_toml, merge_cli_args, parse_nuwa_config
from .discovery import discover_nim_sources, validate_nim_project
from .errors import format_compilation_error, format_compilation_success
from .utils import (
    check_nim_installed,
    get_platform_extension,
    get_wheel_tags,
    install_nimble_dependencies,
)
from .wheel_utils import write_wheel_metadata

logger = logging.getLogger("nuwa")


def _extract_metadata() -> tuple[str, str]:
    """Extract project name and version from pyproject.toml.

    Returns:
        Tuple of (name, version)

    Raises:
        FileNotFoundError: If pyproject.toml not found
        KeyError: If required fields are missing
    """
    pyproject = load_pyproject_toml()

    if not pyproject:
        raise FileNotFoundError(
            "pyproject.toml not found. "
            "This command must be run in a project directory."
        )

    project = pyproject.get("project", {})

    if "name" not in project:
        raise KeyError("Missing required field [project.name] in pyproject.toml")

    name = project["name"]
    version = project.get("version", "0.1.0")

    return name, version


def _determine_inplace_output(module_name: str, config: dict) -> Path:
    """Determine output path for in-place compilation.

    Args:
        module_name: Python module name
        config: Configuration dictionary

    Returns:
        Path where compiled extension should be placed
    """
    output_location = config["output_location"]
    lib_name = config["lib_name"]
    ext = get_platform_extension()

    if output_location == "auto":
        # Use flat layout: my_package/
        out_dir = Path(module_name)
    elif output_location == "src":
        # Explicit src layout (for backward compatibility)
        out_dir = Path("src") / module_name
    else:
        # Explicit path
        out_dir = Path(output_location)

    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / f"{lib_name}{ext}"


def _build_nim_command(
    entry_point: Path,
    output_path: Path,
    build_type: str,
    nim_flags: list,
    nim_dir: Path
) -> list[str]:
    """Build the Nim compiler command.

    Args:
        entry_point: Path to entry point .nim file
        output_path: Where to write the compiled extension
        build_type: "debug" or "release"
        nim_flags: Additional compiler flags from config
        nim_dir: Nim source directory (for module path)

    Returns:
        List of command arguments
    """
    cmd = [
        "nim",
        "c",
        "--app:lib",
        f"--out:{output_path}",
    ]

    # Add module search path (so imports work between Nim files)
    cmd.append(f"--path:{nim_dir}")

    # Add release flag
    if build_type == "release":
        cmd.append("-d:release")

    # Add user flags
    if nim_flags:
        cmd.extend(nim_flags)

    # Add entry point
    cmd.append(str(entry_point))

    return cmd


def _compile_nim(
    build_type: str = "release",
    inplace: bool = False,
    config_overrides: Optional[dict] = None
) -> Path:
    """Compile the Nim extension.

    Args:
        build_type: "debug" or "release"
        inplace: If True, compile next to source; if False, compile to build dir
        config_overrides: Optional config dict (for testing or CLI overrides)

    Returns:
        Path to compiled .so/.pyd file

    Raises:
        RuntimeError: If Nim compiler is not found
        FileNotFoundError: If sources not found
        subprocess.CalledProcessError: If compilation fails
    """
    # Check Nim is installed
    check_nim_installed()

    # Load configuration
    config = parse_nuwa_config()
    if config_overrides:
        config = merge_cli_args(config, config_overrides)

    # Install nimble dependencies if configured
    nimble_deps = config.get("nimble_deps", [])
    if nimble_deps:
        install_nimble_dependencies(nimble_deps)

    # Discover sources
    nim_dir, entry_point = discover_nim_sources(config)
    validate_nim_project(nim_dir, entry_point)

    # Determine output path
    module_name = config["module_name"]
    lib_name = config["lib_name"]
    ext = get_platform_extension()

    if inplace:
        # For develop/editable: place in Python package directory
        out_path = _determine_inplace_output(module_name, config)
    else:
        # For wheels: place in current working directory
        out_path = Path.cwd() / f"{lib_name}{ext}"

    logger.info(f"Compiling {entry_point} -> {out_path}")
    print(f"🐍 Nuwa: Compiling {entry_point} -> {out_path}...")

    # Build compiler command
    cmd = _build_nim_command(
        entry_point=entry_point,
        output_path=out_path,
        build_type=build_type,
        nim_flags=config["nim_flags"],
        nim_dir=nim_dir
    )

    # Run compilation
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False
        )

        if result.returncode != 0:
            # Format and display error with context
            formatted_error = format_compilation_error(
                result.stderr,
                working_dir=Path.cwd()
            )
            print(formatted_error)
            raise subprocess.CalledProcessError(result.returncode, cmd)

        # Log warnings and hints
        if result.stderr:
            warnings_hints = []
            for line in result.stderr.splitlines():
                if "Hint:" in line or "Warning:" in line:
                    warnings_hints.append(line)

            if warnings_hints:
                logger.debug("Compiler warnings/hints:")
                for warning in warnings_hints:
                    logger.debug(f"  {warning}")

    except FileNotFoundError:
        raise RuntimeError(
            f"Nim compiler not found at '{shutil.which('nim')}'.\n"
            "Install Nim from https://nim-lang.org/install.html"
        ) from None

    # Success
    logger.debug(f"Successfully compiled {out_path}")
    print(format_compilation_success(out_path))
    return out_path


# --- PEP 517 Hooks ---

def build_wheel(
    wheel_directory: str,
    config_settings: Optional[dict] = None,  # noqa: ARG001
    metadata_directory: Optional[str] = None  # noqa: ARG001
) -> str:
    """Build a standard wheel.

    Args:
        wheel_directory: Directory to write the wheel
        config_settings: Optional build settings
        metadata_directory: Optional metadata directory

    Returns:
        The wheel filename
    """
    so_file = _compile_nim(build_type="release", inplace=False)

    # Extract metadata
    name, version = _extract_metadata()
    config = parse_nuwa_config()
    lib_name = config["lib_name"]
    ext = get_platform_extension()

    # Build wheel with proper tags
    wheel_name = get_wheel_tags(name, version)
    wheel_path = Path(wheel_directory) / wheel_name

    with zipfile.ZipFile(wheel_path, "w") as zf:
        # Include Python package files
        package_dir = Path(name)
        if package_dir.exists():
            for py_file in package_dir.rglob("*.py"):
                arcname = str(py_file)
                zf.write(py_file, arcname=arcname)

        # Place .so file inside the package directory
        zf.write(so_file, arcname=f"{name}/{lib_name}{ext}")

        # Write metadata
        write_wheel_metadata(zf, name, version)

    # Cleanup compiled artifact after packing
    if so_file.exists():
        so_file.unlink()

    return wheel_path.name


def build_sdist(
    sdist_directory: str,
    config_settings: Optional[dict] = None  # noqa: ARG001
) -> str:
    """Build a source distribution.

    Args:
        sdist_directory: Directory to write the source distribution
        config_settings: Optional build settings

    Returns:
        The source distribution filename
    """
    import shutil

    # Extract metadata
    name, version = _extract_metadata()

    # Create source distribution archive
    base_name = f"{name}-{version}"
    archive_name = f"{base_name}.tar.gz"
    shutil.make_archive(
        str(Path(sdist_directory) / base_name),
        "gztar",
        root_dir="."
    )

    return archive_name


# --- PEP 660 Hooks (Editable Installs) ---

def build_editable(
    wheel_directory: str,
    config_settings: Optional[dict] = None,  # noqa: ARG001
    metadata_directory: Optional[str] = None  # noqa: ARG001
) -> str:
    """Build an editable wheel (pip install -e .).

    Args:
        wheel_directory: Directory to write the wheel
        config_settings: Optional build settings
        metadata_directory: Optional metadata directory

    Returns:
        The wheel filename
    """
    import zipfile

    # Compile in-place
    _compile_nim(build_type="debug", inplace=True)

    # Extract metadata
    name, version = _extract_metadata()

    # Create editable wheel
    wheel_name = f"{name}-{version}-py3-none-any.whl"
    wheel_path = Path(wheel_directory) / wheel_name

    with zipfile.ZipFile(wheel_path, "w") as zf:
        # Point python to the project root (flat layout)
        zf.writestr(f"{name}.pth", str(Path.cwd()))

        # Write metadata
        write_wheel_metadata(zf, name, version, tag="py3-none-any")

    return wheel_name


# Boilerplate required hooks
def get_requires_for_build_wheel(config_settings: Optional[dict] = None) -> list:  # noqa: ARG001
    """Return build requirements for wheels."""
    return []


def get_requires_for_build_sdist(config_settings: Optional[dict] = None) -> list:  # noqa: ARG001
    """Return build requirements for source distributions."""
    return []


def get_requires_for_build_editable(config_settings: Optional[dict] = None) -> list:  # noqa: ARG001
    """Return build requirements for editable installs."""
    return []
