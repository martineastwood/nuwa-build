"""Tests for optional watch-mode dependencies."""

import argparse
import builtins
from unittest.mock import patch

import pytest

from nuwa_build.watch import run_watch


def test_watch_explains_how_to_install_optional_dependency():
    """Watch mode reports its extra when watchdog is unavailable."""
    real_import = builtins.__import__

    def import_without_watchdog(name, *args, **kwargs):
        if name.startswith("watchdog"):
            raise ModuleNotFoundError("No module named 'watchdog'", name="watchdog")
        return real_import(name, *args, **kwargs)

    with (
        patch("builtins.__import__", side_effect=import_without_watchdog),
        pytest.raises(RuntimeError, match=r"nuwa-build\[watch\]"),
    ):
        run_watch(argparse.Namespace())
