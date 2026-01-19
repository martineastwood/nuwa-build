"""Type stub generation for Nim-compiled Python extensions."""

import json
import logging
from pathlib import Path

logger = logging.getLogger("nuwa")


class StubGenerator:
    """Generates Python type stubs (.pyi files) from compiler metadata."""

    def __init__(self, module_name: str):
        """Initialize the stub generator.

        Args:
            module_name: Name of the Python module (e.g., "my_extension_lib")
        """
        self.module_name = module_name
        self.entries: list[dict] = []

    def parse_compiler_output(self, output: str) -> int:
        """Extract JSON metadata from compiler output.

        Args:
            output: Stdout from Nim compiler containing NUWA_STUB: lines

        Returns:
            Number of stub entries found
        """
        count = 0
        for line in output.splitlines():
            line = line.strip()
            if line.startswith("NUWA_STUB:"):
                try:
                    json_str = line[len("NUWA_STUB:") :].strip()
                    data = json.loads(json_str)
                    self.entries.append(data)
                    count += 1
                    logger.debug(f"Parsed stub metadata for: {data.get('name', '?')}")
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse stub metadata: {line[:80]}...")
                    logger.debug(f"Parse error: {e}")

        return count

    def parse_stubs_from_directory(self, stub_dir: Path) -> int:
        """Extract JSON metadata from files in a directory.

        Args:
            stub_dir: Directory containing JSON stub files

        Returns:
            Number of stub entries found
        """
        if not stub_dir.exists():
            logger.warning(f"Stub directory does not exist: {stub_dir}")
            return 0

        # Find all JSON files in the directory
        json_files = list(stub_dir.glob("*.json"))

        if not json_files:
            logger.debug(f"No JSON files found in stub directory: {stub_dir}")
            return 0

        count = 0
        for json_file in json_files:
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                self.entries.append(data)
                count += 1
                logger.debug(f"Parsed stub metadata from: {json_file.name}")
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse stub file {json_file.name}: {e}")
            except OSError as e:
                logger.warning(f"Failed to read stub file {json_file.name}: {e}")

        return count

    def parse_stubs_from_directory_with_fallback(self, stub_dir: Path, compiler_output: str) -> int:
        """Parse stubs from directory, falling back to stdout parsing.

        This is the recommended method that tries file-based parsing first,
        then falls back to stdout parsing if no files are found.

        Args:
            stub_dir: Directory containing JSON stub files (may not exist)
            compiler_output: Stdout from Nim compiler as fallback

        Returns:
            Number of stub entries found
        """
        # Try file-based approach first
        file_count = self.parse_stubs_from_directory(stub_dir)

        if file_count > 0:
            logger.info(f"Using file-based stub generation: found {file_count} stubs")
            return file_count

        # Fall back to stdout parsing
        logger.info("No stub files found, falling back to stdout parsing")
        return self.parse_compiler_output(compiler_output)

    def generate_pyi(self, output_dir: Path) -> Path:
        """Write the .pyi file to disk.

        Args:
            output_dir: Directory where the .pyi file should be written

        Returns:
            Path to the generated .pyi file
        """
        # Start with imports
        pyi_lines = [f"# Stubs for {self.module_name}", "from typing import Any", ""]

        # Check if we need List import
        needs_list = any(
            "list[" in entry.get("returnType", "")
            or any("list[" in arg.get("type", "") for arg in entry.get("args", []))
            for entry in self.entries
        )
        if needs_list:
            pyi_lines[1] = "from typing import Any, List"

        # Add each function
        for entry in self.entries:
            name = entry["name"]
            ret_type = entry.get("returnType", "None")
            doc = entry.get("doc", "")

            # Format arguments
            args_list = []
            for arg in entry.get("args", []):
                a_name = arg["name"]
                a_type = arg.get("type", "Any")
                has_default = arg.get("hasDefault", False)

                if has_default:
                    args_list.append(f"{a_name}: {a_type} = ...")
                else:
                    args_list.append(f"{a_name}: {a_type}")

            args_str = ", ".join(args_list)

            # Handle functions with no arguments
            if not args_str:
                args_str = ""

            # Build function definition
            func_def = f"def {name}({args_str}) -> {ret_type}:"
            pyi_lines.append(func_def)

            # Add docstring
            if doc and doc.strip():
                doc_lines = doc.strip().split("\n")
                if len(doc_lines) == 1:
                    pyi_lines.append(f'    """{doc}"""')
                else:
                    pyi_lines.append('    """')
                    for line in doc_lines:
                        pyi_lines.append(f"    {line}")
                    pyi_lines.append('    """')

            pyi_lines.append("    ...")
            pyi_lines.append("")  # Blank line between functions

        # Write to disk
        output_dir.mkdir(parents=True, exist_ok=True)
        pyi_path = output_dir / f"{self.module_name}.pyi"
        pyi_path.write_text("\n".join(pyi_lines), encoding="utf-8")
        logger.info(f"Generated type stubs: {pyi_path}")

        return pyi_path


def find_pyi_files(directory: Path) -> list[Path]:
    """Find all .pyi files in a directory.

    Args:
        directory: Directory to search

    Returns:
        List of .pyi file paths
    """
    return list(directory.rglob("*.pyi"))
