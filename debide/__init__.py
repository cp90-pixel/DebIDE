"""DebIDE package exports."""

from importlib.metadata import version, PackageNotFoundError

__all__ = ["__version__"]

try:
    __version__ = version("debide")
except PackageNotFoundError:  # pragma: no cover - local dev fallback
    __version__ = "0.1.0"

