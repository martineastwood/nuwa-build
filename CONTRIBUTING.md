# Contributing to Nuwa Build

Thank you for your interest in contributing to Nuwa Build! This document provides guidelines for contributing.

## Development Setup

### 1. Fork and Clone

```bash
git clone https://github.com/martineastwood/nuwa-build.git
cd nuwa-build
```

### 2. Install Development Dependencies

```bash
# Install nuwa-build in development mode with dev tools
pip install -e ".[dev]"

# Install Nim compiler
# Visit https://nim-lang.org/install.html
# Or use: choosenim install 0.1.0 / choosenim 2.0.0

# Install nimpy
nimble install nimpy
```

### 3. Install Pre-commit Hooks (Optional but Recommended)

```bash
pre-commit install
```

This will automatically run linting and formatting on every commit.

## Development Workflow

### 1. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/your-bug-fix
```

### 2. Make Changes

- Write code following the style guide (see below)
- Add tests for new functionality
- Update documentation as needed

### 3. Run Quality Checks

```bash
# Format code
ruff format src/

# Lint code
ruff check src/

# Type check
mypy src/

# Run tests
pytest tests/unit/ -v

# Run integration tests (requires Nim)
pytest tests/integration/ -v
```

### 4. Commit Changes

```bash
git add .
git commit -m "Brief description of changes"
```

### 5. Push and Create Pull Request

```bash
git push origin feature/your-feature-name
```

Then create a pull request on GitHub.

## Code Style

Use automated tools to maintain consistent code style:

- **Ruff** - Linting and formatting (run `ruff check src/` and `ruff format src/`)
- **MyPy** - Type checking (run `mypy src/`)
- **Pre-commit hooks** - Automatically run on commits (optional)

### Type Hints

All functions should have type hints:

```python
def compile_nim(source: Path, output: Path) -> bool:
    """Compile a Nim file to a shared library.

    Args:
        source: Path to the Nim source file
        output: Path where the compiled library should be written

    Returns:
        True if compilation succeeded, False otherwise
    """
    ...
```

### Documentation

All public functions and classes should have docstrings:

```python
def function_name(param1: str, param2: int) -> bool:
    """Brief description of what the function does.

    Longer description if needed. Explain edge cases, algorithms, etc.

    Args:
        param1: Description of param1
        param2: Description of param2

    Returns:
        Description of return value

    Raises:
        ValueError: If param1 is invalid
    """
    ...
```

## Testing

### Unit Tests

Unit tests should not require external dependencies (like Nim compiler):

```python
def test_parse_nim_error():
    """Test error parsing logic."""
    stderr = "file.nim(10, 5) Error: type mismatch"
    result = parse_nim_error(stderr)
    assert result is not None
    assert result["line"] == 10
```

### Integration Tests

Integration tests require Nim and should test the full compilation workflow:

```python
@pytest.mark.integration
def test_build_simple_project(tmp_path, requires_nim):
    """Test building a simple Nim project."""
    # Create test project
    # Build it
    # Verify it works
```

### Running Tests

```bash
# Run all unit tests (fast, no Nim needed)
pytest tests/unit/ -v

# Run all tests
pytest -v

# Run with coverage
pytest --cov=src/nuwa_build --cov-report=html
```

## Project Structure

```
nuwa-build/
├── src/nuwa_build/       # Main package
│   ├── __init__.py
│   ├── backend.py        # PEP 517 hooks and compilation
│   ├── cli.py            # Command-line interface
│   ├── config.py         # Configuration parsing
│   ├── discovery.py      # Source file discovery
│   ├── errors.py         # Error formatting
│   ├── templates.py      # Project templates
│   ├── utils.py          # Utility functions
│   └── wheel_utils.py    # Wheel building helpers
├── tests/
│   ├── unit/             # Fast tests (no Nim needed)
│   ├── integration/      # Full workflow tests (requires Nim)
│   └── conftest.py       # Pytest configuration and fixtures
├── .github/workflows/    # CI/CD workflows
└── pyproject.toml        # Project configuration
```

## Adding New Features

1. **Discuss first** - Open an issue to discuss the feature before implementing
2. **Update documentation** - Keep README.md and docstrings in sync
3. **Add tests** - Ensure test coverage doesn't decrease
4. **Consider backwards compatibility** - Try not to break existing projects

## Bug Fixes

1. **Add a test** - Write a test that reproduces the bug
2. **Fix the bug** - Make the test pass
3. **Check for regressions** - Run all tests to ensure nothing broke

## Questions?

Feel free to:

- Open an issue for bugs or feature requests
- Start a discussion for questions
- Join us in GitHub Discussions (if enabled)

## Code Review Process

All pull requests go through code review. Maintainers may:

- Request changes to code style
- Ask for additional tests
- Suggest improvements to documentation
- Discuss design decisions

This is collaborative - feel free to discuss and ask questions!

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
