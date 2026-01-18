"""Core compilation functionality for Nuwa Build."""

import logging
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from .config import ConfigResolver, load_pyproject_toml
from .constants import NIM_APP_LIB_FLAG
from .discovery import discover_nim_sources, validate_nim_project
from .errors import format_compilation_error, format_compilation_success
from .stubs import StubGenerator
from .utils import (
    check_nim_installed,
    get_platform_extension,
    install_nimble_dependencies,
)

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
            "pyproject.toml not found. This command must be run in a project directory."
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
    nim_dir: Path,
    nimble_path: Optional[Path] = None,
) -> list[str]:
    """Build the Nim compiler command.

    Args:
        entry_point: Path to entry point .nim file
        output_path: Where to write the compiled extension
        build_type: "debug" or "release"
        nim_flags: Additional compiler flags from config
        nim_dir: Nim source directory (for module path)
        nimble_path: Optional path to local nimble packages directory

    Returns:
        List of command arguments
    """
    cmd = [
        "nim",
        "c",
        NIM_APP_LIB_FLAG,
        f"--out:{output_path}",
    ]

    # Add module search path (so imports work between Nim files)
    cmd.append(f"--path:{nim_dir}")

    # Add local nimble path for isolated dependencies
    if nimble_path:
        # Nimble stores packages in 'pkgs' (older) or 'pkgs2' (newer) subdirectory
        # Check pkgs2 first (preferred in newer nimble versions), then fall back to pkgs
        pkgs_path = nimble_path / "pkgs2"
        if not pkgs_path.exists():
            pkgs_path = nimble_path / "pkgs"
        if pkgs_path.exists():
            cmd.append(f"--nimblePath:{pkgs_path}")

    # Add release flag
    if build_type == "release":
        cmd.append("-d:release")

    # Add user flags
    if nim_flags:
        cmd.extend(nim_flags)

    # Add entry point
    cmd.append(str(entry_point))

    return cmd


def _install_dependencies(config: dict, project_root: Path) -> Path:
    """Install nimble dependencies to local directory if configured.

    Args:
        config: Configuration dictionary
        project_root: Project root directory

    Returns:
        Path to local nimble directory
    """
    local_nimble_path = project_root / ".nimble"

    nimble_deps = config.get("nimble_deps", [])
    if nimble_deps:
        install_nimble_dependencies(nimble_deps, local_dir=local_nimble_path)

    return local_nimble_path


def _determine_output_path(config: dict, inplace: bool) -> Path:
    """Determine output path for compilation.

    Args:
        config: Configuration dictionary
        inplace: If True, compile next to source; if False, compile to build dir

    Returns:
        Path where compiled extension should be placed
    """
    lib_name = config["lib_name"]
    ext = get_platform_extension()

    if inplace:
        # For develop/editable: place in Python package directory
        module_name = config["module_name"]
        return _determine_inplace_output(module_name, config)
    else:
        # For wheels: place in current working directory
        return Path.cwd() / f"{lib_name}{ext}"


def _run_compilation(
    cmd: list[str], entry_point: Path, out_path: Path
) -> subprocess.CompletedProcess:
    """Execute the Nim compiler command.

    Args:
        cmd: Compiler command list
        entry_point: Path to entry point .nim file
        out_path: Output path for compiled extension

    Returns:
        Completed process result

    Raises:
        RuntimeError: If Nim compiler is not found
        subprocess.CalledProcessError: If compilation fails
    """
    logger.info(f"Compiling {entry_point} -> {out_path}")
    print(f"🐍 Nuwa: Compiling {entry_point} -> {out_path}...")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)

        if result.returncode != 0:
            # Format and display error with context
            formatted_error = format_compilation_error(result.stderr, working_dir=Path.cwd())
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

        return result

    except FileNotFoundError:
        raise RuntimeError(
            f"Nim compiler not found at '{shutil.which('nim')}'.\n"
            "Install Nim from https://nim-lang.org/install.html"
        ) from None


def _generate_type_stubs(lib_name: str, compiler_output: str, output_dir: Path) -> None:
    """Generate Python type stubs from compiler output.

    Args:
        lib_name: Name of the compiled library
        compiler_output: Standard output from the compiler
        output_dir: Directory to write .pyi files to
    """
    generator = StubGenerator(lib_name)
    stub_count = generator.parse_compiler_output(compiler_output)

    if stub_count > 0:
        generator.generate_pyi(output_dir)
        logger.info(f"Generated {stub_count} type stubs for {lib_name}")
    else:
        logger.debug("No stub metadata found in compiler output (nuwa_sdk not used?)")


def _setup_build_environment(config: dict) -> tuple[Path, Path, Optional[Path]]:
    """Setup build environment by installing dependencies and discovering sources.

    Args:
        config: Configuration dictionary

    Returns:
        Tuple of (nim_dir, entry_point, local_nimble_path)

    Raises:
        RuntimeError: If Nim compiler is not found
        FileNotFoundError: If sources not found
    """
    # Install dependencies
    project_root = Path.cwd()
    local_nimble_path = _install_dependencies(config, project_root)

    # Discover sources
    nim_dir, entry_point = discover_nim_sources(config)
    validate_nim_project(nim_dir, entry_point)

    return nim_dir, entry_point, local_nimble_path


def _compile_nim(
    build_type: str = "release",
    inplace: bool = False,
    config_overrides: Optional[dict] = None,
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

    # Load and resolve configuration
    resolver = ConfigResolver(cli_overrides=config_overrides)
    config = resolver.resolve()

    # Setup build environment
    nim_dir, entry_point, local_nimble_path = _setup_build_environment(config)

    # Determine output path
    out_path = _determine_output_path(config, inplace)

    # Build compiler command
    cmd = _build_nim_command(
        entry_point=entry_point,
        output_path=out_path,
        build_type=build_type,
        nim_flags=config["nim_flags"],
        nim_dir=nim_dir,
        nimble_path=local_nimble_path,
    )

    # Run compilation
    result = _run_compilation(cmd, entry_point, out_path)

    # Success
    logger.debug(f"Successfully compiled {out_path}")
    print(format_compilation_success(out_path))

    # Generate type stubs
    lib_name = config["lib_name"]
    _generate_type_stubs(lib_name, result.stdout, out_path.parent)

    return out_path
