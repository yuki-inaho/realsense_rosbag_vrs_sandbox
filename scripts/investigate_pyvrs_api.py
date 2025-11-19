#!/usr/bin/env python3
"""Investigate PyVRS API structure.

This script explores the PyVRS module structure and outputs detailed
information about available classes, methods, and functions in Markdown format.
"""

import inspect
import sys
from typing import Any


def investigate_module(module: Any, module_name: str) -> None:
    """Investigate a Python module and print its structure.

    Args:
        module: The module to investigate
        module_name: Name of the module
    """
    print(f"# PyVRS API Investigation\n")
    print(f"**Module:** `{module_name}`\n")
    print(f"**Date:** 2025-11-19\n")
    print("---\n")

    # Top-level attributes
    print("## Top-Level Attributes\n")
    all_attrs = dir(module)

    # Filter out private attributes
    public_attrs = [a for a in all_attrs if not a.startswith("_")]

    print(f"**Total public attributes:** {len(public_attrs)}\n")

    # Categorize attributes
    classes = []
    functions = []
    modules = []
    constants = []

    for attr_name in public_attrs:
        attr = getattr(module, attr_name)
        if inspect.isclass(attr):
            classes.append((attr_name, attr))
        elif inspect.isfunction(attr):
            functions.append((attr_name, attr))
        elif inspect.ismodule(attr):
            modules.append((attr_name, attr))
        else:
            constants.append((attr_name, attr))

    # Print classes
    print(f"## Classes ({len(classes)})\n")
    for class_name, cls in sorted(classes):
        print(f"### `{class_name}`\n")

        # Class docstring
        if cls.__doc__:
            doc_lines = cls.__doc__.strip().split("\n")
            print(f"**Description:** {doc_lines[0]}\n")

        # Methods
        methods = [m for m in dir(cls) if not m.startswith("_") or m in ["__init__", "__enter__", "__exit__"]]
        if methods:
            print(f"**Methods:** {len(methods)}\n")
            for method_name in sorted(methods):
                try:
                    method = getattr(cls, method_name)
                    if callable(method):
                        sig = inspect.signature(method)
                        print(f"- `{method_name}{sig}`")
                except Exception:
                    print(f"- `{method_name}` (signature unavailable)")
            print()
        print()

    # Print functions
    print(f"## Functions ({len(functions)})\n")
    for func_name, func in sorted(functions):
        try:
            sig = inspect.signature(func)
            print(f"- `{func_name}{sig}`")
            if func.__doc__:
                doc_lines = func.__doc__.strip().split("\n")
                print(f"  - {doc_lines[0]}")
        except Exception:
            print(f"- `{func_name}` (signature unavailable)")
    print()

    # Print submodules
    print(f"## Submodules ({len(modules)})\n")
    for mod_name, mod in sorted(modules):
        print(f"### `{mod_name}`\n")
        if mod.__doc__:
            doc_lines = mod.__doc__.strip().split("\n")
            print(f"**Description:** {doc_lines[0]}\n")

        # List public attributes of submodule
        submod_attrs = [a for a in dir(mod) if not a.startswith("_")]
        print(f"**Public attributes:** {len(submod_attrs)}")
        print(f"- {', '.join(sorted(submod_attrs[:20]))}")
        if len(submod_attrs) > 20:
            print(f"  ... and {len(submod_attrs) - 20} more")
        print()

    # Print constants
    if constants:
        print(f"## Constants/Other ({len(constants)})\n")
        for const_name, const in sorted(constants):
            const_type = type(const).__name__
            print(f"- `{const_name}`: `{const_type}`")
        print()

    print("---\n")
    print("## Key Findings\n")
    print("### Reader Classes\n")
    reader_classes = [c for c, _ in classes if "Reader" in c]
    for rc in reader_classes:
        print(f"- `{rc}`: Used for reading VRS files")
    print()

    print("### Record Classes\n")
    record_classes = [c for c, _ in classes if "Record" in c]
    for rc in record_classes:
        print(f"- `{rc}`: Represents VRS records")
    print()

    print("### Spec Classes\n")
    spec_classes = [c for c, _ in classes if "Spec" in c]
    for sc in spec_classes:
        print(f"- `{sc}`: Configuration specifications")
    print()

    print("### Note\n")
    print("- **Module name:** The package is named `vrs` but must be imported as `pyvrs`")
    print("- **Writer support:** No explicit Writer class found in top-level API")
    print("  - VRS writing may be done through C++ bindings or different interface")
    print("  - Further investigation of submodules may be needed")


def main() -> int:
    """Main entry point."""
    try:
        import pyvrs

        investigate_module(pyvrs, "pyvrs")

        return 0
    except ImportError as e:
        print(f"Error: Failed to import pyvrs: {e}", file=sys.stderr)
        print("Make sure PyVRS is installed: uv pip install vrs", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
