"""Configuration management for Nuwa Build."""

import sys
from typing import Any, Optional

from .utils import (
    DEFAULT_NIM_SOURCE_DIR,
    DEFAULT_OUTPUT_LOCATION,
    normalize_package_name,
)

# Python 3.11+ has tomllib built-in, otherwise use tomli
if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None  # type: ignore[assignment, unused-ignore]

__all__ = [
    "tomllib",
    "load_pyproject_toml",
    "parse_nuwa_config",
    "build_config_overrides",
    "merge_cli_args",
]


def load_pyproject_toml() -> dict[str, Any]:
    """Load and parse pyproject.toml.

    Returns:
        Parsed TOML data, or empty dict if file not found
    """
    if tomllib is None:
        raise RuntimeError("Cannot parse pyproject.toml. Install tomli: pip install tomli")

    try:
        with open("pyproject.toml", "rb") as f:
            data: dict[str, Any] = tomllib.load(f)
            return data
    except FileNotFoundError:
        return {}


def _validate_config_fields(config: dict[str, Any]) -> None:
    """Validate configuration has all required fields and valid values.

    Args:
        config: Configuration dictionary to validate

    Raises:
        ValueError: If required fields are missing or invalid
    """
    required_fields = ["nim_source", "module_name", "lib_name", "entry_point"]
    missing = [field for field in required_fields if field not in config]

    if missing:
        raise ValueError(f"Missing required configuration fields: {missing}")

    if not config["module_name"].isidentifier():
        raise ValueError(
            f"Module name '{config['module_name']}' is not a valid Python identifier. "
            f"Use only letters, numbers, and underscores, and don't start with a number."
        )

    if not config["nim_source"].strip():
        raise ValueError("nim_source cannot be empty")


def parse_nuwa_config(profile: Optional[str] = None) -> dict[str, Any]:
    """Parse Nuwa configuration from pyproject.toml with defaults.

    Reads [tool.nuwa] section from pyproject.toml and merges with defaults.
    Derives module name from [project.name] if not explicitly set.

    Args:
        profile: Optional profile name to apply from [tool.nuwa.profiles]

    Returns:
        Configuration dictionary

    Raises:
        ValueError: If configuration is invalid
        RuntimeError: If tomli is not installed (Python < 3.11)
    """
    pyproject = load_pyproject_toml()

    if not pyproject:
        project_name = "nuwa_project"
        nuwa = {}
    else:
        project = pyproject.get("project", {})
        project_name = project.get("name", "nuwa_project")
        nuwa = pyproject.get("tool", {}).get("nuwa", {})

    # Build config with defaults
    module_name = nuwa.get("module-name") or normalize_package_name(project_name)
    lib_name = nuwa.get("lib-name") or f"{module_name}_lib"

    config = {
        "nim_source": nuwa.get("nim-source", DEFAULT_NIM_SOURCE_DIR),
        "module_name": module_name,
        "lib_name": lib_name,
        "entry_point": nuwa.get("entry-point", f"{lib_name}.nim"),
        "output_location": nuwa.get("output-location", DEFAULT_OUTPUT_LOCATION),
        "nim_flags": list(nuwa.get("nim-flags", [])),
        "bindings": nuwa.get("bindings", "nimpy"),
        "nimble_deps": list(nuwa.get("nimble-deps", [])),
        "allow_manifest_binaries": bool(nuwa.get("allow-manifest-binaries", False)),
        "windows_static_linking": bool(nuwa.get("windows-static-linking", True)),
        "bundle_adjacent_dlls": bool(nuwa.get("bundle-adjacent-dlls", True)),
    }

    # Apply profile if specified
    if profile:
        profiles = nuwa.get("profiles", {})
        if profile not in profiles:
            available = ", ".join(profiles.keys()) if profiles else "none"
            raise ValueError(f"Unknown profile '{profile}'. Available profiles: {available}")
        profile_config = profiles[profile]
        profile_flags = profile_config.get("nim-flags", [])
        # Extend base flags with profile flags (profile flags come after for override behavior)
        config["nim_flags"].extend(profile_flags)

    _validate_config_fields(config)

    if (
        sys.platform == "win32"
        and config.get("windows_static_linking", False)
        and "--passL:-static" not in config["nim_flags"]
        and "--cc:vcc" not in config["nim_flags"]
    ):
        config["nim_flags"].append("--passL:-static")

    return config


def build_config_overrides(**kwargs: Optional[Any]) -> dict[str, Any]:
    """Build a config overrides dictionary from keyword arguments.

    Filters out None values, returning only the actual overrides.
    This provides a consistent way to build configuration overrides
    across CLI, magic, and other contexts.

    Args:
        **kwargs: Configuration override values (e.g., module_name="foo", nim_source="bar")

    Returns:
        Dictionary containing only the non-None overrides

    Example:
        >>> build_config_overrides(module_name="foo", nim_source=None)
        {'module_name': 'foo'}
    """
    return {k: v for k, v in kwargs.items() if v is not None}


def merge_cli_args(config: dict[str, Any], cli_args: dict[str, Any]) -> dict[str, Any]:
    """Merge CLI argument overrides into config.

    CLI arguments take precedence over config file values.

    Args:
        config: Base configuration from pyproject.toml
        cli_args: Dictionary of CLI argument overrides

    Returns:
        Merged configuration dictionary
    """
    result = config.copy()

    # Map CLI arg keys to config keys (direct overrides)
    cli_to_config_map = {
        "module_name": "module_name",
        "nim_source": "nim_source",
        "entry_point": "entry_point",
        "allow_manifest_binaries": "allow_manifest_binaries",
        "windows_static_linking": "windows_static_linking",
        "bundle_adjacent_dlls": "bundle_adjacent_dlls",
    }

    for cli_key, config_key in cli_to_config_map.items():
        if cli_args.get(cli_key):
            result[config_key] = cli_args[cli_key]

    # output_location/output_dir -> output_location (different key names)
    if "output_location" in cli_args and cli_args["output_location"] is not None:
        result["output_location"] = cli_args["output_location"]
    elif "output_dir" in cli_args and cli_args["output_dir"] is not None:
        result["output_location"] = cli_args["output_dir"]

    # nim_flags: extend existing flags (don't replace)
    if cli_args.get("nim_flags"):
        result["nim_flags"] = result.get("nim_flags", []) + cli_args["nim_flags"]

    return result
