"""Nuwa Build - The Maturin for Nim."""

__version__ = "0.3.5"

from .pep517_hooks import (
    build_editable,
    build_sdist,
    build_wheel,
    get_requires_for_build_editable,
    get_requires_for_build_sdist,
    get_requires_for_build_wheel,
)

__all__ = [
    "__version__",
    "build_wheel",
    "build_sdist",
    "build_editable",
    "get_requires_for_build_wheel",
    "get_requires_for_build_sdist",
    "get_requires_for_build_editable",
]

# Optional IPython integration
try:
    from .magic import load_ipython_extension  # noqa: F401

    __all__.append("load_ipython_extension")
except ImportError:
    # IPython not installed, skip magic commands
    pass
