"""Choice Signal user interface: the Signal Hub entry point.

The only package under ``choicesignal`` that imports Streamlit or Plotly. ``render()`` draws the whole app on the
current page and never calls ``st.set_page_config``; the standalone ``app.py`` or Signal Hub owns the page config.
"""

from choicesignal import __version__
from choicesignal.ui import signal_theme
from choicesignal.ui.app import render

APP_INFO = {"product": "Choice Signal", "version": __version__, "repo": "conjoint-analysis", "slug": "choice"}

__all__ = ["APP_INFO", "render", "signal_theme"]
