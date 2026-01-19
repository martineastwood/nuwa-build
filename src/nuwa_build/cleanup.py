"""Build artifact cleanup functionality for Nuwa Build."""

import logging
import shutil
import sys
from pathlib import Path
from typing import Optional

from .config import parse_nuwa_config

logger = logging.getLogger("nuwa")


class CleanupResult:
    """Result of a cleanup operation."""

    def __init__(self, cleaned: Optional[list[str]] = None, errors: Optional[list[str]] = None):
        """Initialize cleanup result.

        Args:
            cleaned: List of cleaned items
            errors: List of error messages
        """
        self.cleaned = cleaned or []
        self.errors = errors or []

    def has_cleaned(self) -> bool:
        """Check if any items were cleaned."""
        return len(self.cleaned) > 0

    def has_errors(self) -> bool:
        """Check if any errors occurred."""
        return len(self.errors) > 0

    def merge(self, other: "CleanupResult") -> None:
        """Merge another result into this one.

        Args:
            other: Another CleanupResult to merge
        """
        self.cleaned.extend(other.cleaned)
        self.errors.extend(other.errors)


class BuildArtifactCleaner:
    """Clean build artifacts and dependencies from Nuwa projects."""

    def __init__(self, project_root: Optional[Path] = None):
        """Initialize the cleaner.

        Args:
            project_root: Project root directory (defaults to current working directory)
        """
        self.project_root = project_root or Path.cwd()

    def _safe_remove_dir(self, path: Path, name: str) -> CleanupResult:
        """Safely remove a directory if it exists.

        Args:
            path: Path to directory
            name: Display name for the directory

        Returns:
            CleanupResult with outcome
        """
        result = CleanupResult()
        if path.exists() and path.is_dir():
            try:
                shutil.rmtree(path)
                result.cleaned.append(f"{name}/")
            except OSError as e:
                result.errors.append(f"{name}/: {e}")
                logger.warning(f"Failed to remove {path}: {e}")
        return result

    def _safe_remove_file(self, path: Path) -> CleanupResult:
        """Safely remove a file if it exists and is not a symlink.

        Args:
            path: Path to file

        Returns:
            CleanupResult with outcome
        """
        result = CleanupResult()
        if path.exists() and path.is_file():
            # Skip symlinks to avoid deleting the target
            if path.is_symlink():
                return result
            try:
                path.unlink()
                # Try to get relative path, fall back to absolute if it fails
                try:
                    display_path = str(path.relative_to(self.project_root))
                except ValueError:
                    display_path = str(path)
                result.cleaned.append(display_path)
            except OSError as e:
                result.errors.append(f"{path}: {e}")
                logger.warning(f"Failed to remove {path}: {e}")
        return result

    def clean_nimble_dependencies(self) -> CleanupResult:
        """Clean the .nimble/ directory.

        Returns:
            CleanupResult with outcome
        """
        nimble_path = self.project_root / ".nimble"
        return self._safe_remove_dir(nimble_path, ".nimble")

    def clean_nimcache(self) -> CleanupResult:
        """Clean the nimcache/ directory.

        Returns:
            CleanupResult with outcome
        """
        nimcache_path = self.project_root / "nimcache"
        return self._safe_remove_dir(nimcache_path, "nimcache")

    def clean_nuwacache(self) -> CleanupResult:
        """Clean the .nuwacache/ directory.

        Returns:
            CleanupResult with outcome
        """
        nuwacache_path = self.project_root / ".nuwacache"
        return self._safe_remove_dir(nuwacache_path, ".nuwacache")

    def clean_build_directory(self) -> CleanupResult:
        """Clean the build/ directory.

        Returns:
            CleanupResult with outcome
        """
        build_path = self.project_root / "build"
        return self._safe_remove_dir(build_path, "build")

    def clean_dist_directory(self) -> CleanupResult:
        """Clean the dist/ directory.

        Returns:
            CleanupResult with outcome
        """
        dist_path = self.project_root / "dist"
        return self._safe_remove_dir(dist_path, "dist")

    def clean_compiled_extensions(self) -> CleanupResult:
        """Clean compiled .so/.pyd files from Nuwa-managed locations.

        Returns:
            CleanupResult with outcome
        """
        result = CleanupResult()

        try:
            config = parse_nuwa_config()
            lib_name = config.get("lib_name", "")
            module_name = config.get("module_name", "")
            ext = ".pyd" if sys.platform == "win32" else ".so"

            # Only remove the specific compiled extension that Nuwa generates
            if lib_name:
                # Check in common output locations
                for output_dir in [Path(module_name), Path("src") / module_name]:
                    if output_dir.exists():
                        ext_file = output_dir / f"{lib_name}{ext}"
                        result.merge(self._safe_remove_file(ext_file))

        except FileNotFoundError as e:
            # pyproject.toml not found - not a Nuwa project
            logger.debug(f"No pyproject.toml found, skipping artifact cleaning: {e}")
            result.errors.append(
                "Could not load pyproject.toml (not a Nuwa project?). "
                "Skipping compiled artifact cleanup."
            )
        except KeyError as e:
            # Config missing required fields
            logger.warning(f"Config missing required field for artifact cleaning: {e}")
            result.errors.append(f"Config error: missing field {e}. Skipping artifact cleanup.")
        except (OSError, ValueError) as e:
            # I/O errors or invalid config values
            logger.error(f"Error during artifact cleaning: {e}", exc_info=True)
            result.errors.append(
                f"Error cleaning artifacts: {type(e).__name__}: {e}\n"
                f"Compiled extensions may not have been cleaned. Try manually deleting .so/.pyd files."
            )

        return result

    def clean_dependencies(self) -> CleanupResult:
        """Clean all dependencies (.nimble/).

        Returns:
            CleanupResult with outcome
        """
        return self.clean_nimble_dependencies()

    def clean_artifacts(self) -> CleanupResult:
        """Clean all build artifacts (nimcache/, .nuwacache/, build/, dist/, compiled extensions).

        Returns:
            CleanupResult with outcome
        """
        result = CleanupResult()
        result.merge(self.clean_nimcache())
        result.merge(self.clean_nuwacache())
        result.merge(self.clean_build_directory())
        result.merge(self.clean_dist_directory())
        result.merge(self.clean_compiled_extensions())
        return result

    def clean_all(self) -> CleanupResult:
        """Clean all dependencies and artifacts.

        Returns:
            CleanupResult with outcome
        """
        result = CleanupResult()
        result.merge(self.clean_dependencies())
        result.merge(self.clean_artifacts())
        return result
