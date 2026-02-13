"""Type stub generation for Nim-compiled Python extensions."""

import json
from pathlib import Path


class StubGenerator:
    """Generates Python type stubs (.pyi files) from compiler metadata."""

    def __init__(self, module_name: str):
        """Initialize the stub generator.

        Args:
            module_name: Name of the Python module (e.g., "my_extension_lib")
        """
        self.module_name = module_name
        self.entries: list[dict] = []

    def parse_stubs(self, stub_dir: Path, compiler_output: str) -> int:
        """Parse stubs from directory or stdout (fallback).

        Tries file-based parsing first, falls back to stdout parsing if no files found.

        Args:
            stub_dir: Directory containing JSON stub files (may not exist)
            compiler_output: Stdout from Nim compiler as fallback

        Returns:
            Number of stub entries found
        """
        # Try file-based approach first
        if stub_dir.exists():
            json_files = list(stub_dir.glob("*.json"))
            if json_files:
                count = 0
                for json_file in json_files:
                    try:
                        data = json.loads(json_file.read_text(encoding="utf-8"))
                        self.entries.append(data)
                        count += 1
                    except (json.JSONDecodeError, OSError) as e:
                        print(f"Warning: Failed to read stub file {json_file.name}: {e}")
                return count

        # Fall back to stdout parsing
        count = 0
        for line in compiler_output.splitlines():
            line = line.strip()
            if line.startswith("NUWA_STUB:"):
                try:
                    json_str = line[len("NUWA_STUB:") :].strip()
                    data = json.loads(json_str)
                    self.entries.append(data)
                    count += 1
                except json.JSONDecodeError:
                    print(f"Warning: Failed to parse stub metadata: {line[:80]}...")

        return count

    def generate_pyi(self, output_dir: Path) -> Path:
        """Write the .pyi file to disk.

        Args:
            output_dir: Directory where the .pyi file should be written

        Returns:
            Path to the generated .pyi file
        """
        # Start with imports (use modern lowercase list, no typing.List needed)
        pyi_lines = [f"# Stubs for {self.module_name}", "from typing import Any", ""]

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

            # Build function definition with ruff-compatible formatting
            # Use multi-line style if there are 3+ arguments (ruff's heuristic)
            if len(args_list) >= 3:
                # Multi-line format
                pyi_lines.append(f"def {name}(")
                for arg_line in args_list:
                    pyi_lines.append(f"    {arg_line},")
                pyi_lines.append(f") -> {ret_type}:")
            else:
                # Single-line format
                args_str = ", ".join(args_list)
                if not args_str:
                    args_str = ""
                pyi_lines.append(f"def {name}({args_str}) -> {ret_type}:")

            # Add docstring
            if doc and doc.strip():
                doc_lines = doc.strip().split("\n")
                if len(doc_lines) == 1:
                    pyi_lines.append(f'    """{doc}"""')
                else:
                    pyi_lines.append('    """')
                    for line in doc_lines:
                        # Strip trailing whitespace and skip empty lines to avoid ruff warnings
                        stripped = line.rstrip()
                        if stripped:  # Only add non-empty lines
                            pyi_lines.append(f"    {stripped}")
                        else:
                            pyi_lines.append("")  # Preserve paragraph breaks as empty lines
                    pyi_lines.append('    """')

            pyi_lines.append("    ...")
            pyi_lines.append("")  # Blank line between functions

        # Write to disk
        output_dir.mkdir(parents=True, exist_ok=True)
        pyi_path = output_dir / f"{self.module_name}.pyi"
        pyi_path.write_text("\n".join(pyi_lines), encoding="utf-8")

        return pyi_path
