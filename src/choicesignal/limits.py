"""Data limits: none on your own computer, hard caps only in a public demo.

Run locally (standalone, a local Signal Hub or an internal company deployment), Choice Signal imposes no limit on
file size, rows, cells, respondents, attributes or levels; the computer's memory and processor are the limit. The
one bound kept locally is the exhaustive optimal-design search (conjoint.EXHAUSTIVE_SEARCH_CELLS), which grows
combinatorially. A public demo sets ``SIGNAL_PUBLIC=1`` and then every cap below applies, to protect a shared
server. Every demo cap lives in this module.
"""

from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Limits:
    """Caps in force; ``None`` means unlimited."""

    upload_bytes: int | None = None
    json_bytes: int | None = None
    expanded_workbook_bytes: int | None = None
    table_rows: int | None = None
    total_cells: int | None = None
    rating_rows: int | None = None
    attributes: int | None = None
    levels_per_attribute: int | None = None
    search_cells: int | None = None


LOCAL = Limits()
PUBLIC_DEMO = Limits(
    upload_bytes=200 * 1024 * 1024,
    json_bytes=50 * 1024 * 1024,
    expanded_workbook_bytes=400 * 1024 * 1024,
    table_rows=1_000_000,
    total_cells=10_000_000,
    rating_rows=500_000,
    attributes=10,
    levels_per_attribute=12,
    search_cells=20_000_000,
)
DEMO_NOTE = "This is a limit of the public demo; the downloaded app has none."


def is_public() -> bool:
    """True in a public demo (``SIGNAL_PUBLIC=1``), read at call time."""
    return os.environ.get("SIGNAL_PUBLIC") == "1"


def active() -> Limits:
    return PUBLIC_DEMO if is_public() else LOCAL


def demo_limit(message: str) -> str:
    """A capped message that says it is a demo limit and that the downloaded app has none."""
    return f"{message} {DEMO_NOTE}"
