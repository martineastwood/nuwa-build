"""Core compilation functionality for Nuwa Build."""

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

# Configure UTF-8 encoding for Windows compatibility
if sys.platform == "win32":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

from .config import load_pyproject_toml, merge_cli_args, parse_nuwa_config
from .discovery import discover_nim_sources, validate_nim_entry_point
from .errors import format_compilation_error
from .stubs import StubGenerator
from .utils import (
    NIM_APP_LIB_FLAG,
    NIMBLE_PKGS2_DIR,
    NIMBLE_PKGS_DIR,
    OUTPUT_LOCATION_AUTO,
    OUTPUT_LOCATION_SRC,
    RELEASE_FLAG,
    check_nim_installed,
    get_platform_extension,
    install_nimble_dependencies,
    temp_directory,
)


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


def _build_nim_command(
    entry_point: Path,
    output_path: Path,
    build_type: str,
    nim_flags: list,
    nim_dir: Path,
    nimble_path: Optional[Path] = None,
    stub_dir: Optional[Path] = None,
) -> list[str]:
    """Build the Nim compiler command.

    Args:
        entry_point: Path to entry point .nim file
        output_path: Where to write the compiled extension
        build_type: "debug" or "release"
        nim_flags: Additional compiler flags from config
        nim_dir: Nim source directory (for module path)
        nimble_path: Optional path to local nimble packages directory
        stub_dir: Optional path to directory for stub file generation

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
        pkgs_path = nimble_path / NIMBLE_PKGS2_DIR
        if not pkgs_path.exists():
            pkgs_path = nimble_path / NIMBLE_PKGS_DIR
        if pkgs_path.exists():
            cmd.append(f"--nimblePath:{pkgs_path}")

    # Add release flag
    if build_type == "release":
        cmd.append(RELEASE_FLAG)

    # Add stub directory flag if provided
    if stub_dir is not None:
        cmd.append(f"-d:nuwaStubDir={stub_dir}")

    # Add user flags
    if nim_flags:
        cmd.extend(nim_flags)

    # Add entry point
    cmd.append(str(entry_point))

    return cmd


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
    print(f"🐍 Nuwa: Compiling {entry_point} -> {out_path}...")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)

        # Log warnings and hints from successful compilations
        if result.stderr:
            warnings_hints = []
            for line in result.stderr.splitlines():
                if "Hint:" in line or "Warning:" in line:
                    warnings_hints.append(line)

            if warnings_hints:
                for warning in warnings_hints:
                    print(f"  {warning}")

        return result

    except subprocess.CalledProcessError as e:
        # Format and display error with context
        formatted_error = format_compilation_error(e.stderr, working_dir=Path.cwd())
        print(formatted_error)
        raise
    except FileNotFoundError:
        raise RuntimeError(
            f"Nim compiler not found at '{shutil.which('nim')}'.\n"
            "Install Nim from https://nim-lang.org/install.html"
        ) from None


def _compile_nim(
    build_type: str = "release",
    inplace: bool = False,
    config_overrides: Optional[dict] = None,
    entry_point_content: Optional[str] = None,
    nim_dir_override: Optional[Path] = None,
    skip_nimble_deps: bool = False,
) -> Path:
    """Compile the Nim extension.

    Args:
        build_type: "debug" or "release"
        inplace: If True, compile next to source; if False, compile to build dir
        config_overrides: Optional config dict (for testing or CLI overrides)
        entry_point_content: Optional string content to write to entry point (for Jupyter)
        nim_dir_override: Optional nim directory path (to skip discovery)
        skip_nimble_deps: If True, skip nimble dependency installation

    Returns:
        Path to compiled extension file (platform-specific extension)

    Raises:
        RuntimeError: If Nim compiler is not found
        FileNotFoundError: If sources not found
        subprocess.CalledProcessError: If compilation fails
    """
    # Check Nim is installed
    check_nim_installed()

    # Load and resolve configuration
    # Extract profile from config_overrides if present (it's not a standard config key)
    profile = None
    if config_overrides:
        profile = config_overrides.pop("profile", None)

    config = parse_nuwa_config(profile=profile)
    if config_overrides:
        config = merge_cli_args(config, config_overrides)

    # Skip nimble deps if requested (for Jupyter)
    if skip_nimble_deps:
        config = config.copy()
        config["nimble_deps"] = []

    # Install nimble dependencies if configured
    project_root = Path.cwd()
    local_nimble_path = project_root / ".nimble"
    nimble_deps = config.get("nimble_deps", [])
    if nimble_deps:
        install_nimble_dependencies(nimble_deps, local_dir=local_nimble_path)

    # Discover or use provided sources
    if nim_dir_override is not None:
        nim_dir = nim_dir_override
        lib_name = config["lib_name"]
        entry_point = nim_dir / f"{lib_name}.nim"

        # Write entry point content if provided
        if entry_point_content is not None:
            entry_point.parent.mkdir(parents=True, exist_ok=True)
            entry_point.write_text(entry_point_content)
    else:
        nim_dir, entry_point = discover_nim_sources(config)

    validate_nim_entry_point(entry_point)

    # Determine output path
    lib_name = config["lib_name"]
    ext = get_platform_extension()

    if inplace:
        # For develop/editable: place in Python package directory
        module_name = config["module_name"]
        output_location = config["output_location"]

        if output_location == OUTPUT_LOCATION_AUTO:
            out_dir = Path(module_name)
        elif output_location == OUTPUT_LOCATION_SRC:
            out_dir = Path("src") / module_name
        else:
            out_dir = Path(output_location)

        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{lib_name}{ext}"
    else:
        # For wheels: place in current working directory
        out_path = Path.cwd() / f"{lib_name}{ext}"

    # Create temporary directory for stub files and run compilation
    with temp_directory() as stub_dir:
        # Build compiler command
        cmd = _build_nim_command(
            entry_point=entry_point,
            output_path=out_path,
            build_type=build_type,
            nim_flags=config["nim_flags"],
            nim_dir=nim_dir,
            nimble_path=local_nimble_path,
            stub_dir=stub_dir,
        )

        # Run compilation
        result = _run_compilation(cmd, entry_point, out_path)

        # Success
        size_mb = out_path.stat().st_size / (1024 * 1024)
        print(f"✅ Built {out_path.name} ({size_mb:.2f} MB)")

        # Generate type stubs
        generator = StubGenerator(lib_name)
        stub_count = generator.parse_stubs(
            stub_dir=stub_dir,
            compiler_output=result.stdout,
        )

        if stub_count > 0:
            generator.generate_pyi(out_path.parent)
            print(f"Generated {stub_count} type stubs for {lib_name}")

    # Temp directory is automatically cleaned up here

    return out_path
