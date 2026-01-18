"""Configuration management for Nuwa Build."""

import sys
from typing import Any, Optional

# Python 3.11+ has tomllib built-in, otherwise use tomli
if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None  # type: ignore[assignment, unused-ignore]


def get_default_config(project_name: str = "nuwa_project") -> dict[str, Any]:
    """Return default configuration.

    Args:
        project_name: Project name used to derive module name

    Returns:
        Dictionary with default configuration values
    """
    from .utils import normalize_package_name

    module_name = normalize_package_name(project_name)
    lib_name = f"{module_name}_lib"
    return {
        "nim_source": "nim",
        "module_name": module_name,
        "lib_name": lib_name,
        "entry_point": f"{lib_name}.nim",
        "output_location": "auto",
        "nim_flags": [],
        "bindings": "nimpy",
        "nimble_deps": [],
    }


def validate_config(config: dict[str, Any]) -> None:
    """Validate configuration has all required fields.

    Args:
        config: Configuration dictionary to validate

    Raises:
        ValueError: If required fields are missing or invalid
    """
    required_fields = ["nim_source", "module_name", "lib_name", "entry_point"]
    missing = [field for field in required_fields if field not in config]

    if missing:
        raise ValueError(f"Missing required configuration fields: {missing}")

    # Validate module name is a valid Python identifier
    module_name = config["module_name"]
    if not module_name.isidentifier():
        raise ValueError(
            f"Module name '{module_name}' is not a valid Python identifier. "
            f"Use only letters, numbers, and underscores, and don't start with a number."
        )

    # Validate nim_source is not empty
    if not config["nim_source"].strip():
        raise ValueError("nim_source cannot be empty")


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


def parse_nuwa_config() -> dict[str, Any]:
    """Parse Nuwa configuration from pyproject.toml with defaults.

    Reads [tool.nuwa] section from pyproject.toml and merges with defaults.
    Derives module name from [project.name] if not explicitly set.

    Returns:
        Configuration dictionary

    Raises:
        ValueError: If configuration is invalid
    """
    pyproject = load_pyproject_toml()

    if not pyproject:
        return get_default_config()

    # Extract project metadata
    project = pyproject.get("project", {})
    project_name = project.get("name", "nuwa_project")

    # Extract Nuwa-specific config
    nuwa = pyproject.get("tool", {}).get("nuwa", {})

    config = get_default_config(project_name)

    # Override with explicit config values
    if "nim-source" in nuwa:
        config["nim_source"] = nuwa["nim-source"]
    if "module-name" in nuwa:
        config["module_name"] = nuwa["module-name"]
    if "lib-name" in nuwa:
        config["lib_name"] = nuwa["lib-name"]
    if "entry-point" in nuwa:
        config["entry_point"] = nuwa["entry-point"]
    if "output-location" in nuwa:
        config["output_location"] = nuwa["output-location"]
    if "nim-flags" in nuwa:
        config["nim_flags"] = list(nuwa["nim-flags"])  # Ensure it's a list
    if "bindings" in nuwa:
        config["bindings"] = nuwa["bindings"]
    if "nimble-deps" in nuwa:
        config["nimble_deps"] = list(nuwa["nimble-deps"])  # Ensure it's a list

    # Validate the final configuration
    validate_config(config)

    return config


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

    if cli_args.get("module_name"):
        result["module_name"] = cli_args["module_name"]
    if cli_args.get("nim_source"):
        result["nim_source"] = cli_args["nim_source"]
    if cli_args.get("entry_point"):
        result["entry_point"] = cli_args["entry_point"]
    if cli_args.get("output_dir"):
        result["output_location"] = cli_args["output_dir"]
    if cli_args.get("nim_flags"):
        # Extend existing flags (don't replace)
        result["nim_flags"] = result.get("nim_flags", []) + cli_args["nim_flags"]

    return result


class ConfigResolver:
    """Centralized configuration resolution with CLI override support.

    This class encapsulates the workflow of loading configuration from pyproject.toml,
    applying CLI overrides, and validating the result.
    """

    def __init__(self, cli_overrides: Optional[dict[str, Any]] = None):
        """Initialize the ConfigResolver.

        Args:
            cli_overrides: Optional dictionary of CLI argument overrides
        """
        self.cli_overrides = cli_overrides

    def resolve(self) -> dict[str, Any]:
        """Load, merge, and validate configuration.

        Returns:
            Resolved configuration dictionary

        Raises:
            ValueError: If configuration is invalid
        """
        config = parse_nuwa_config()

        if self.cli_overrides:
            config = merge_cli_args(config, self.cli_overrides)

        return config
