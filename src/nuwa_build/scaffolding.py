"""Project scaffolding utilities for Nuwa Build."""

from pathlib import Path

from .config import tomllib
from .templates import (
    BUILD_SYSTEM_SECTION,
    GITIGNORE,
    HELPERS_NIM,
    LIB_NIM,
    TOOL_NUWA_SECTION,
)


def determine_project_name(path: Path, pyproject_path: Path) -> str:
    """Determine project name from pyproject.toml or directory name.

    Args:
        path: Project path
        pyproject_path: Path to pyproject.toml

    Returns:
        Project name
    """
    project_name = "my_project"
    if pyproject_path.exists():
        try:
            with open(pyproject_path, "rb") as f:
                pyproject = tomllib.load(f)
                project_name = pyproject.get("project", {}).get("name", project_name)
        except (OSError, tomllib.TOMLDecodeError):
            # Fallback if file is currently unreadable or invalid TOML
            project_name = path.resolve().name
    else:
        project_name = path.resolve().name

    return project_name


def update_pyproject_toml(pyproject_path: Path, module_name: str, project_name: str) -> None:
    """Update or create pyproject.toml with Nuwa configuration.

    Args:
        pyproject_path: Path to pyproject.toml
        module_name: Python module name
        project_name: Project name
    """
    if pyproject_path.exists():
        try:
            with open(pyproject_path, "rb") as f:
                current_config = tomllib.load(f)
        except (OSError, tomllib.TOMLDecodeError):
            print("❌ Error: Existing pyproject.toml is invalid. Cannot modify safely.")
            return

        # CHECK 1: Build System
        # We only append if [build-system] is COMPLETELY missing
        if "build-system" in current_config:
            backend = current_config["build-system"].get("build-backend", "legacy")
            if backend != "nuwa_build":
                print(f"⚠️  Warning: Project uses another build backend ('{backend}').")
                print("   To use Nuwa, you must manually edit pyproject.toml:")
                print("   [build-system]")
                print('   requires = ["nuwa-build"]')
                print('   build-backend = "nuwa_build"')
            else:
                print("✅ Build backend already configured.")
        else:
            print("➕ Adding [build-system] to pyproject.toml")
            with open(pyproject_path, "a", encoding="utf-8") as f:
                f.write(BUILD_SYSTEM_SECTION)

        # CHECK 2: Tool Config
        # We only append if [tool.nuwa] is COMPLETELY missing
        if "tool" in current_config and "nuwa" in current_config["tool"]:
            print("ℹ️  [tool.nuwa] configuration already exists.")
        else:
            print("➕ Adding [tool.nuwa] config to pyproject.toml")
            with open(pyproject_path, "a", encoding="utf-8") as f:
                f.write(TOOL_NUWA_SECTION.format(module_name=module_name))
    else:
        # Create fresh pyproject.toml
        print("📄 Creating pyproject.toml")
        with open(pyproject_path, "w", encoding="utf-8") as f:
            f.write(f'[project]\nname = "{project_name}"\nversion = "0.1.0"\n')
            f.write(BUILD_SYSTEM_SECTION)
            f.write(TOOL_NUWA_SECTION.format(module_name=module_name))


def create_nim_scaffolding(path: Path, module_name: str, lib_name: str) -> None:
    """Create Nim directory structure and source files.

    Args:
        path: Project path
        module_name: Python module name
        lib_name: Library name for compiled extension
    """
    nim_dir = path / "nim"
    if not nim_dir.exists():
        print("📄 Creating nim/ directory")
        nim_dir.mkdir(exist_ok=True)

        # Entry point
        entry_file = nim_dir / f"{lib_name}.nim"
        if not entry_file.exists():
            print(f"📄 Creating nim/{entry_file.name}")
            with open(entry_file, "w", encoding="utf-8") as f:
                f.write(LIB_NIM.format(module_name=module_name))

        # Helpers
        helpers_file = nim_dir / "helpers.nim"
        if not helpers_file.exists():
            print("📄 Creating nim/helpers.nim")
            with open(helpers_file, "w", encoding="utf-8") as f:
                f.write(HELPERS_NIM.format(module_name=module_name))
    else:
        print("ℹ️  nim/ directory already exists. Skipping Nim scaffolding.")


def update_gitignore(path: Path) -> None:
    """Update or create .gitignore with Nuwa build artifacts.

    Args:
        path: Project path
    """
    gitignore_path = path / ".gitignore"
    if gitignore_path.exists():
        git_content = gitignore_path.read_text(encoding="utf-8")
        if "*.so" not in git_content and "*.pyd" not in git_content:
            print("➕ Adding build artifacts to .gitignore")
            with open(gitignore_path, "a", encoding="utf-8") as f:
                f.write(
                    "\n# Nuwa Build Artifacts\n*.so\n*.so.*\n*.pyd\n*.pyd.*\nnimcache/\n.nimble/\ndist/\n"
                )
    else:
        print("📄 Creating .gitignore")
        with open(gitignore_path, "w", encoding="utf-8") as f:
            f.write(GITIGNORE)


def create_python_package_scaffolding(path: Path, module_name: str) -> None:
    """Create Python package directory and __init__.py.

    Args:
        path: Project path
        module_name: Python module name
    """
    from .templates import INIT_PY

    package_dir = path / module_name
    package_dir.mkdir(parents=True, exist_ok=True)

    init_file = package_dir / "__init__.py"
    if not init_file.exists():
        print(f"📄 Creating {module_name}/__init__.py")
        with open(init_file, "w", encoding="utf-8") as f:
            f.write(INIT_PY.format(module_name=module_name))


def create_tests_scaffolding(path: Path, module_name: str) -> None:
    """Create tests directory and test file.

    Args:
        path: Project path
        module_name: Python module name
    """
    from .templates import TEST_PY

    tests_dir = path / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)

    test_file = tests_dir / f"test_{module_name}.py"
    if not test_file.exists():
        print(f"📄 Creating tests/test_{module_name}.py")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(TEST_PY.format(module_name=module_name))


def create_example_file(path: Path, module_name: str) -> None:
    """Create example.py file.

    Args:
        path: Project path
        module_name: Python module name
    """
    from .templates import EXAMPLE_PY

    example_file = path / "example.py"
    if not example_file.exists():
        print("📄 Creating example.py")
        with open(example_file, "w", encoding="utf-8") as f:
            f.write(EXAMPLE_PY.format(module_name=module_name))


def create_readme(path: Path, project_name: str, module_name: str) -> None:
    """Create README.md file.

    Args:
        path: Project path
        project_name: Project name
        module_name: Python module name
    """
    from .templates import README_MD

    readme_file = path / "README.md"
    if not readme_file.exists():
        print("📄 Creating README.md")
        with open(readme_file, "w", encoding="utf-8") as f:
            f.write(README_MD.format(project_name=project_name, module_name=module_name))


def create_github_actions(path: Path) -> None:
    """Create GitHub Actions workflow directory and file.

    Args:
        path: Project path
    """
    from .templates import GITHUB_ACTIONS_PUBLISH_YML

    workflows_dir = path / ".github" / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)

    workflow_file = workflows_dir / "publish.yml"
    if not workflow_file.exists():
        print("📄 Creating .github/workflows/publish.yml")
        with open(workflow_file, "w", encoding="utf-8") as f:
            f.write(GITHUB_ACTIONS_PUBLISH_YML)
