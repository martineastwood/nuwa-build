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
