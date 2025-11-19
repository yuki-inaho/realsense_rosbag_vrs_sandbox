"""Test PyVRS module import.

This test verifies that PyVRS can be imported successfully.
"""

import pytest


def test_pyvrs_import() -> None:
    """Test that pyvrs module can be imported."""
    import pyvrs

    assert pyvrs is not None


def test_pyvrs_has_required_modules() -> None:
    """Test that pyvrs has required submodules."""
    import pyvrs

    # Check for key modules based on directory listing
    assert hasattr(pyvrs, "reader")
    assert hasattr(pyvrs, "base")
    assert hasattr(pyvrs, "record")
    assert hasattr(pyvrs, "utils")
