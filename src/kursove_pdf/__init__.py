"""Public Python interface: generate_pdf(payload) -> bytes."""

from .renderer import generate_pdf
from .validation import InputError

__all__ = ["generate_pdf", "InputError"]
__version__ = "1.1.0"
