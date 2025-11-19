"""pyvrs_writer: Python bindings for VRS file writing.

This package provides a Python interface to write VRS (Virtual Reality Stream)
files using the VRS C++ library.
"""

from pathlib import Path
import sys

# C++拡張モジュールのインポート
try:
    from ._pyvrs_writer import VRSWriter
except ImportError as e:
    raise ImportError(
        f"Failed to import C++ extension module: {e}\n"
        "Make sure the module is built and installed correctly."
    ) from e

__version__ = "0.1.0"
__all__ = ["VRSWriter"]
