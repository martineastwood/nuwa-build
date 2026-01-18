"""Core compilation functionality for Nuwa Build."""

import logging
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

from wheel.wheelfile import WheelFile

from .config import load_pyproject_toml, merge_cli_args, parse_nuwa_config
from .constants import NIM_APP_LIB_FLAG
from .discovery import discover_nim_sources, validate_nim_project
from .errors import format_compilation_error, format_compilation_success
from .stubs import StubGenerator
from .utils import (
    check_nim_installed,
    get_platform_extension,
    get_wheel_tags,
    install_nimble_dependencies,
)
from .wheel_utils import write_wheel_metadata

logger = logging.getLogger("nuwa")


def _extract_metadata() -> Tuple[str, str]:
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
    nim_flags: List,
    nim_dir: Path,
    nimble_path: Optional[Path] = None,
) -> List[str]:
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
    cmd: List[str], entry_point: Path, out_path: Path
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

    # Load configuration
    config = parse_nuwa_config()
    if config_overrides:
        config = merge_cli_args(config, config_overrides)

    # Install dependencies
    project_root = Path.cwd()
    local_nimble_path = _install_dependencies(config, project_root)

    # Discover sources
    nim_dir, entry_point = discover_nim_sources(config)
    validate_nim_project(nim_dir, entry_point)

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


# --- PEP 517 Hooks ---


def _add_python_package_files(wf: WheelFile, name_normalized: str) -> None:
    """Add Python package files to the wheel.

    Args:
        wf: WheelFile object to write to
        name_normalized: Normalized package name
    """
    package_dir = Path(name_normalized)
    if package_dir.exists():
        for py_file in package_dir.rglob("*.py"):
            arcname = str(py_file)
            wf.write(str(py_file), arcname=arcname)


def _add_compiled_extension(
    wf: WheelFile,
    so_file: Path,
    name_normalized: str,
    lib_name: str,
    ext: str,
) -> None:
    """Add compiled extension to the wheel.

    Args:
        wf: WheelFile object to write to
        so_file: Path to compiled .so/.pyd file
        name_normalized: Normalized package name
        lib_name: Library name (without extension)
        ext: Platform-specific extension (.so/.pyd)
    """
    arcname = f"{name_normalized}/{lib_name}{ext}"
    # Write with proper permissions for shared library
    wf.write(str(so_file), arcname=arcname)


def _add_type_stubs(
    wf: WheelFile,
    so_file: Path,
    name_normalized: str,
    lib_name: str,
) -> None:
    """Add type stub files to the wheel if they exist.

    Args:
        wf: WheelFile object to write to
        so_file: Path to compiled .so/.pyd file
        name_normalized: Normalized package name
        lib_name: Library name
    """
    pyi_file = so_file.with_suffix(".pyi")
    if pyi_file.exists():
        arcname = f"{name_normalized}/{lib_name}.pyi"
        wf.write(str(pyi_file), arcname=arcname)
        logger.info(f"Including type stubs: {lib_name}.pyi")


def _add_wheel_metadata(
    wf: WheelFile,
    name: str,
    version: str,
    wheel_tag: str,
    name_normalized: str,
) -> None:
    """Add WHEEL and METADATA files to the wheel.

    Args:
        wf: WheelFile object to write to
        name: Package name
        version: Package version
        wheel_tag: Wheel tag (e.g., "cp313-cp313-linux_x86_64")
        name_normalized: Normalized package name
    """
    dist_info = f"{name_normalized}-{version}.dist-info"

    wheel_content = (
        f"Wheel-Version: 1.0\nGenerator: nuwa\nRoot-Is-Purelib: false\nTag: {wheel_tag}\n"
    )
    wf.writestr(f"{dist_info}/WHEEL", wheel_content)

    metadata_content = f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n"
    wf.writestr(f"{dist_info}/METADATA", metadata_content)


def _cleanup_build_artifacts(so_file: Path) -> None:
    """Clean up temporary build artifacts.

    Args:
        so_file: Path to compiled extension
    """
    if so_file.exists():
        so_file.unlink()
    pyi_file = so_file.with_suffix(".pyi")
    if pyi_file.exists():
        pyi_file.unlink()


def build_wheel(
    wheel_directory: str,
    config_settings: Optional[dict] = None,
    metadata_directory: Optional[str] = None,  # noqa: ARG001
) -> str:
    """Build a standard wheel with valid RECORD and permissions.

    Uses wheel.WheelFile which automatically handles:
    - RECORD file generation with proper hashes
    - PEP 427 compliance
    - File permissions and metadata

    Args:
        wheel_directory: Directory to write the wheel
        config_settings: Optional build settings (supports config_overrides)
        metadata_directory: Optional metadata directory

    Returns:
        The wheel filename
    """
    # Convert config_settings to config_overrides format if provided
    config_overrides = None
    if config_settings and "config_overrides" in config_settings:
        config_overrides = config_settings["config_overrides"]

    so_file = _compile_nim(build_type="release", inplace=False, config_overrides=config_overrides)

    # Extract metadata
    name, version = _extract_metadata()
    config = parse_nuwa_config()
    lib_name = config["lib_name"]
    ext = get_platform_extension()

    # Normalize package name
    name_normalized = name.replace("-", "_")

    # Get wheel name and extracted tag
    wheel_name = get_wheel_tags(name, version)
    wheel_tag = wheel_name[:-4].split("-", 2)[2]
    wheel_path = Path(wheel_directory) / wheel_name

    # Use WheelFile for automatic RECORD generation
    with WheelFile(wheel_path, "w") as wf:
        # 1. Add Python package files
        _add_python_package_files(wf, name_normalized)

        # 2. Add compiled extension
        _add_compiled_extension(wf, so_file, name_normalized, lib_name, ext)

        # 3. Add type stubs
        _add_type_stubs(wf, so_file, name_normalized, lib_name)

        # 4. Add metadata
        _add_wheel_metadata(wf, name, version, wheel_tag, name_normalized)

    # Cleanup
    _cleanup_build_artifacts(so_file)

    return wheel_path.name


def build_sdist(
    sdist_directory: str,
    config_settings: Optional[dict] = None,  # noqa: ARG001
) -> str:
    """Build a source distribution.

    Args:
        sdist_directory: Directory to write the source distribution
        config_settings: Optional build settings

    Returns:
        The source distribution filename
    """

    # Extract metadata
    name, version = _extract_metadata()

    # Create source distribution archive
    base_name = f"{name}-{version}"
    archive_name = f"{base_name}.tar.gz"
    shutil.make_archive(str(Path(sdist_directory) / base_name), "gztar", root_dir=".")

    return archive_name


# --- PEP 660 Hooks (Editable Installs) ---


def build_editable(
    wheel_directory: str,
    config_settings: Optional[dict] = None,  # noqa: ARG001
    metadata_directory: Optional[str] = None,  # noqa: ARG001
) -> str:
    """Build an editable wheel (pip install -e .).

    Args:
        wheel_directory: Directory to write the wheel
        config_settings: Optional build settings
        metadata_directory: Optional metadata directory

    Returns:
        The wheel filename
    """

    # Compile in-place
    _compile_nim(build_type="debug", inplace=True)

    # Extract metadata
    name, version = _extract_metadata()

    # Normalize package name: replace hyphens with underscores
    # Per PEP 427, wheel filenames must use underscores even if the package name uses hyphens
    name_normalized = name.replace("-", "_")

    # Create editable wheel
    wheel_name = f"{name_normalized}-{version}-py3-none-any.whl"
    wheel_path = Path(wheel_directory) / wheel_name

    with WheelFile(wheel_path, "w") as wf:
        # Point python to the project root (flat layout)
        wf.writestr(f"{name}.pth", str(Path.cwd()))

        # Write metadata
        write_wheel_metadata(wf, name, version, tag="py3-none-any")

    return wheel_name


# Boilerplate required hooks
def get_requires_for_build_wheel(
    config_settings: Optional[dict] = None,  # noqa: ARG001
) -> list:
    """Return build requirements for wheels."""
    return []


def get_requires_for_build_sdist(
    config_settings: Optional[dict] = None,  # noqa: ARG001
) -> list:
    """Return build requirements for source distributions."""
    return []


def get_requires_for_build_editable(
    config_settings: Optional[dict] = None,  # noqa: ARG001
) -> list:
    """Return build requirements for editable installs."""
    return []
