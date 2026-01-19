"""Unit tests for Jupyter magic commands."""

import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from IPython.core.interactiveshell import InteractiveShell

from nuwa_build.magic import NuwaMagics
from nuwa_build.utils import get_platform_extension


@pytest.fixture
def mock_shell():
    """Create a mock IPython shell."""
    shell = InteractiveShell()
    shell.user_ns = {}
    return shell


@pytest.fixture
def magic(mock_shell):
    """Create a NuwaMagics instance for testing."""
    m = NuwaMagics(shell=mock_shell)
    # Use a temp cache directory for testing
    m.CACHE_DIR = Path(".nuwacache_test")
    m._ensure_cache_dir()
    yield m
    # Cleanup
    if m.CACHE_DIR.exists():
        shutil.rmtree(m.CACHE_DIR)


class TestNuwaMagics:
    """Test NuwaMagics class."""

    def test_parse_magic_line_empty(self, magic):
        """Test parsing empty line."""
        flags = magic._parse_magic_line("")
        assert flags == []

    def test_parse_magic_line_single_flag(self, magic):
        """Test parsing single compiler flag."""
        flags = magic._parse_magic_line("-d:release")
        assert flags == ["-d:release"]

    def test_parse_magic_line_multiple_flags(self, magic):
        """Test parsing multiple compiler flags."""
        flags = magic._parse_magic_line("-d:release --opt:speed")
        assert flags == ["-d:release", "--opt:speed"]

    def test_parse_magic_line_whitespace(self, magic):
        """Test parsing with extra whitespace."""
        flags = magic._parse_magic_line("  -d:release  --opt:speed  ")
        assert flags == ["-d:release", "--opt:speed"]

    def test_compute_hash(self, magic):
        """Test hash computation."""
        code1 = "proc add(): int = 42"
        code2 = "proc add(): int = 42"
        code3 = "proc add(): int = 43"

        hash1 = magic._compute_hash(code1, [])
        hash2 = magic._compute_hash(code2, [])
        hash3 = magic._compute_hash(code3, [])

        # Same code produces same hash
        assert hash1 == hash2

        # Different code produces different hash
        assert hash1 != hash3

        # Hash is hexadecimal string
        assert len(hash1) == 64  # SHA-256 = 64 hex chars
        assert all(c in "0123456789abcdef" for c in hash1)

    def test_compute_hash_with_flags(self, magic):
        """Test hash computation includes flags."""
        code = "proc add(): int = 42"

        hash1 = magic._compute_hash(code, ["-d:release"])
        hash2 = magic._compute_hash(code, ["-d:debug"])
        hash3 = magic._compute_hash(code, ["-d:release"])

        # Different flags produce different hash
        assert hash1 != hash2

        # Same flags produce same hash
        assert hash1 == hash3

    def test_compute_hash_flag_ordering(self, magic):
        """Test that flag order doesn't affect hash."""
        code = "proc add(): int = 42"

        hash1 = magic._compute_hash(code, ["-d:release", "--opt:speed"])
        hash2 = magic._compute_hash(code, ["--opt:speed", "-d:release"])

        # Flags are sorted, so order doesn't matter
        assert hash1 == hash2

    def test_find_cached_extension_exists(self, magic):
        """Test finding cached extension when it exists."""
        # Create mock cached extension
        module_name = "nuwa_test123"
        module_path = magic.CACHE_DIR / module_name
        ext = get_platform_extension()
        ext_file = module_path / f"{module_name}_lib{ext}"
        ext_file.parent.mkdir(parents=True, exist_ok=True)
        ext_file.write_text("mock")

        result = magic._find_cached_extension(magic.CACHE_DIR, module_name)

        assert result == ext_file

    def test_find_cached_extension_missing(self, magic):
        """Test finding cached extension when it doesn't exist."""
        module_name = "nuwa_missing"
        module_path = magic.CACHE_DIR / module_name
        module_path.mkdir(parents=True, exist_ok=True)
        result = magic._find_cached_extension(magic.CACHE_DIR, module_name)

        assert result is None

    def test_extract_exported_functions(self, magic):
        """Test extracting exported functions from module."""
        # Create mock module
        mock_module = MagicMock()

        # Add some functions
        def public_func():
            pass

        def _private_func():
            pass

        mock_module.public_func = public_func
        mock_module._private_func = _private_func
        mock_module.not_callable = "not a function"

        functions = magic._extract_exported_functions(mock_module)

        # Should include public callable
        assert "public_func" in functions

        # Should not include private
        assert "_private_func" not in functions

        # Should not include non-callables
        assert "not_callable" not in functions

    def test_generate_minimal_pyproject(self, magic):
        """Test pyproject.toml generation."""
        module_name = "nuwa_test_module"
        cache_dir = magic.CACHE_DIR / "test_gen"
        cache_dir.mkdir(parents=True, exist_ok=True)

        result = magic._generate_minimal_pyproject(module_name, cache_dir)

        assert result.exists()
        content = result.read_text()

        # Check key fields
        assert f'name = "{module_name}"' in content
        assert 'version = "0.1.0"' in content
        assert f'module-name = "{module_name}"' in content
        assert f'lib-name = "{module_name}_lib"' in content
        assert f'entry-point = "{module_name}_lib.nim"' in content

    @patch("nuwa_build.magic.get_ipython")
    def test_inject_compiled_module(self, mock_get_ipython, magic):
        """Test injecting compiled module into namespace."""
        # Mock IPython shell
        mock_shell = MagicMock()
        mock_shell.user_ns = {}
        mock_get_ipython.return_value = mock_shell

        # Create mock module
        mock_module = MagicMock()

        def test_func():
            return 42

        mock_module.test_func = test_func
        mock_module._private = lambda: None

        # Mock importlib
        with patch("nuwa_build.magic.importlib") as mock_importlib:
            mock_importlib.util.spec_from_file_location.return_value = MagicMock()
            mock_importlib.util.module_from_spec.return_value = mock_module

            # Create mock extension file
            ext = get_platform_extension()
            so_path = magic.CACHE_DIR / f"test{ext}"
            so_path.write_text("mock")

            # Inject
            injected = magic._inject_compiled_module(so_path, "nuwa_test")

            # Check functions were injected
            assert "test_func" in injected
            assert "_private" not in injected
            assert mock_shell.user_ns["test_func"] == test_func

    def test_nuwa_clean(self, magic):
        """Test cache cleanup magic."""
        # Create some files in cache
        test_file = magic.CACHE_DIR / "test.txt"
        test_file.write_text("test")

        # Run cleanup
        magic.nuwa_clean("")

        # Cache should be cleared but directory recreated
        assert magic.CACHE_DIR.exists()
        assert not test_file.exists()

    def test_nuwa_cache_info_empty(self, magic):
        """Test cache info with empty cache."""
        import io
        from contextlib import redirect_stdout

        # Clear cache
        if magic.CACHE_DIR.exists():
            shutil.rmtree(magic.CACHE_DIR)

        # Capture output
        f = io.StringIO()
        with redirect_stdout(f):
            magic.nuwa_cache_info("")

        output = f.getvalue()
        assert "Cache: empty" in output

    def test_nuwa_cache_info_with_modules(self, magic):
        """Test cache info with cached modules."""
        import io
        from contextlib import redirect_stdout

        # Create mock cached modules
        module1 = magic.CACHE_DIR / "nuwa_module1"
        module2 = magic.CACHE_DIR / "nuwa_module2"
        ext = get_platform_extension()

        for m in [module1, module2]:
            m.mkdir()
            (m / f"test{ext}").write_text("x" * 1024)  # 1KB file

        # Capture output
        f = io.StringIO()
        with redirect_stdout(f):
            magic.nuwa_cache_info("")

        output = f.getvalue()
        assert "2 modules" in output
        assert "KB" in output
        assert str(magic.CACHE_DIR.absolute()) in output


def test_load_ipython_extension():
    """Test load_ipython_extension function."""
    from nuwa_build.magic import load_ipython_extension

    mock_ipython = MagicMock()

    load_ipython_extension(mock_ipython)

    # Should register magic class
    mock_ipython.register_magics.assert_called_once()
