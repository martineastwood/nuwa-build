"""Tests for stub generation functionality."""

import json
import tempfile
from pathlib import Path

from nuwa_build.stubs import StubGenerator


class TestStubGeneratorFileParsing:
    """Tests for file-based stub parsing."""

    def test_parse_stubs_with_valid_files(self):
        """Test parsing stubs from directory with valid JSON files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            stub_dir = Path(temp_dir)

            # Create sample stub files
            stub1 = {
                "name": "add",
                "returnType": "int",
                "args": [
                    {"name": "a", "type": "int", "hasDefault": False},
                    {"name": "b", "type": "int", "hasDefault": False},
                ],
                "doc": "Add two numbers",
            }
            stub2 = {
                "name": "greet",
                "returnType": "string",
                "args": [{"name": "name", "type": "string", "hasDefault": False}],
                "doc": "Return a greeting",
            }

            (stub_dir / "add_abc123.json").write_text(json.dumps(stub1))
            (stub_dir / "greet_def456.json").write_text(json.dumps(stub2))

            # Parse
            generator = StubGenerator("test_lib")
            count = generator.parse_stubs(stub_dir, "")

            assert count == 2
            assert len(generator.entries) == 2

            # Get names (order not guaranteed)
            names = {entry["name"] for entry in generator.entries}
            assert names == {"add", "greet"}

    def test_parse_stubs_from_nonexistent_directory(self):
        """Test parsing from nonexistent directory returns 0."""
        generator = StubGenerator("test_lib")
        count = generator.parse_stubs(Path("/nonexistent/path"), "")
        assert count == 0

    def test_parse_stubs_from_empty_directory(self):
        """Test parsing from empty directory returns 0."""
        with tempfile.TemporaryDirectory() as temp_dir:
            stub_dir = Path(temp_dir)
            generator = StubGenerator("test_lib")
            count = generator.parse_stubs(stub_dir, "")
            assert count == 0

    def test_parse_stubs_handles_invalid_json(self):
        """Test that invalid JSON files are skipped with warning."""
        with tempfile.TemporaryDirectory() as temp_dir:
            stub_dir = Path(temp_dir)

            # Valid file
            valid_stub = {"name": "func1", "returnType": "int", "args": []}
            (stub_dir / "func1.json").write_text(json.dumps(valid_stub))

            # Invalid file
            (stub_dir / "invalid.json").write_text("{invalid json")

            generator = StubGenerator("test_lib")
            count = generator.parse_stubs(stub_dir, "")

            # Should parse valid file and skip invalid one
            assert count == 1
            assert len(generator.entries) == 1
            assert generator.entries[0]["name"] == "func1"

    def test_fallback_to_stdout_parsing(self):
        """Test that fallback to stdout parsing works."""
        with tempfile.TemporaryDirectory() as temp_dir:
            stub_dir = Path(temp_dir)

            # Empty directory (no files)
            compiler_output = 'NUWA_STUB: {"name": "add", "returnType": "int", "args": []}'

            generator = StubGenerator("test_lib")
            count = generator.parse_stubs(stub_dir=stub_dir, compiler_output=compiler_output)

            assert count == 1
            assert len(generator.entries) == 1
            assert generator.entries[0]["name"] == "add"

    def test_file_based_mode_preferred_over_stdout(self):
        """Test that file-based mode is preferred when files exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            stub_dir = Path(temp_dir)

            # Create stub file
            stub_file = {"name": "from_file", "returnType": "int", "args": []}
            (stub_dir / "func.json").write_text(json.dumps(stub_file))

            # Also provide stdout (should be ignored)
            compiler_output = 'NUWA_STUB: {"name": "from_stdout", "returnType": "int", "args": []}'

            generator = StubGenerator("test_lib")
            count = generator.parse_stubs(stub_dir=stub_dir, compiler_output=compiler_output)

            # Should use file-based mode, ignore stdout
            assert count == 1
            assert len(generator.entries) == 1
            assert generator.entries[0]["name"] == "from_file"


class TestStubGeneratorIntegration:
    """Integration tests for stub generation."""

    def test_generate_pyi_from_file_based_stubs(self):
        """Test .pyi file generation from file-based stubs."""
        with tempfile.TemporaryDirectory() as temp_dir:
            stub_dir = Path(temp_dir)
            output_dir = Path(temp_dir) / "output"
            output_dir.mkdir()

            # Create stub file
            stub = {
                "name": "add",
                "returnType": "int",
                "args": [
                    {"name": "a", "type": "int", "hasDefault": False},
                    {"name": "b", "type": "int", "hasDefault": False},
                ],
                "doc": "Add two integers",
            }
            (stub_dir / "add.json").write_text(json.dumps(stub))

            # Generate
            generator = StubGenerator("test_lib")
            generator.parse_stubs(stub_dir, "")
            pyi_path = generator.generate_pyi(output_dir)

            # Verify
            assert pyi_path.exists()
            content = pyi_path.read_text()
            assert "def add(a: int, b: int) -> int:" in content
            assert "Add two integers" in content

    def test_generate_pyi_with_multiple_functions(self):
        """Test .pyi file generation with multiple functions."""
        with tempfile.TemporaryDirectory() as temp_dir:
            stub_dir = Path(temp_dir)
            output_dir = Path(temp_dir) / "output"
            output_dir.mkdir()

            # Create multiple stub files
            stub1 = {
                "name": "add",
                "returnType": "int",
                "args": [
                    {"name": "x", "type": "int", "hasDefault": False},
                    {"name": "y", "type": "int", "hasDefault": False},
                ],
                "doc": "Add numbers",
            }
            stub2 = {
                "name": "greet",
                "returnType": "str",
                "args": [{"name": "name", "type": "str", "hasDefault": False}],
                "doc": "Greet someone",
            }
            stub3 = {
                "name": "calculate",
                "returnType": "float",
                "args": [
                    {"name": "value", "type": "float", "hasDefault": True},
                ],
                "doc": "Calculate something",
            }

            (stub_dir / "add.json").write_text(json.dumps(stub1))
            (stub_dir / "greet.json").write_text(json.dumps(stub2))
            (stub_dir / "calculate.json").write_text(json.dumps(stub3))

            # Generate
            generator = StubGenerator("mylib")
            generator.parse_stubs(stub_dir, "")
            pyi_path = generator.generate_pyi(output_dir)

            # Verify
            content = pyi_path.read_text()
            assert "def add(x: int, y: int) -> int:" in content
            assert "def greet(name: str) -> str:" in content
            assert "def calculate(value: float = ...) -> float:" in content
            assert "Add numbers" in content
            assert "Greet someone" in content
            assert "Calculate something" in content

    def test_generate_pyi_with_list_types(self):
        """Test .pyi file generation with list type annotations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            stub_dir = Path(temp_dir)
            output_dir = Path(temp_dir) / "output"
            output_dir.mkdir()

            # Create stub with list types
            stub = {
                "name": "process_items",
                "returnType": "list[str]",
                "args": [{"name": "items", "type": "list[int]", "hasDefault": False}],
                "doc": "Process a list of items",
            }
            (stub_dir / "process.json").write_text(json.dumps(stub))

            # Generate
            generator = StubGenerator("test_lib")
            generator.parse_stubs(stub_dir, "")
            pyi_path = generator.generate_pyi(output_dir)

            # Verify modern lowercase list types are used (PEP 585)
            content = pyi_path.read_text()
            assert "from typing import Any" in content
            assert "List" not in content  # Should use lowercase list
            assert "def process_items(items: list[int]) -> list[str]:" in content

    def test_generate_pyi_with_multiline_docstring(self):
        """Test .pyi file generation with multiline docstrings."""
        with tempfile.TemporaryDirectory() as temp_dir:
            stub_dir = Path(temp_dir)
            output_dir = Path(temp_dir) / "output"
            output_dir.mkdir()

            # Create stub with multiline docstring
            stub = {
                "name": "complex_func",
                "returnType": "bool",
                "args": [],
                "doc": "This is a complex function.\nIt does many things.\nMultiple lines here.",
            }
            (stub_dir / "complex.json").write_text(json.dumps(stub))

            # Generate
            generator = StubGenerator("test_lib")
            generator.parse_stubs(stub_dir, "")
            pyi_path = generator.generate_pyi(output_dir)

            # Verify multiline docstring formatting
            content = pyi_path.read_text()
            assert '    """' in content
            assert "This is a complex function." in content
            assert "It does many things." in content
            assert "Multiple lines here." in content
