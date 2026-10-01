"""Signal Hub contract: importable UI entry point, Streamlit only under ui/, slug-namespaced state."""

import ast
from pathlib import Path
import re
import subprocess
import sys

import pytest
from streamlit.testing.v1 import AppTest

from choicesignal import __version__


ROOT = Path(__file__).parents[1]
PACKAGE = ROOT / "src" / "choicesignal"
UI = PACKAGE / "ui"
UI_ONLY_LIBRARIES = {"streamlit", "plotly"}
PAGES = [
    "Welcome",
    "1 · Data & design",
    "2 · Utilities & importance",
    "3 · Simulate & export",
    "4 · Concept test",
    "Methods & limits",
]
DEMOS = ["demo_coffee_ratings.csv", "demo_car_ratings.csv", "demo_streaming_ratings.csv", "demo_concept_test.csv"]
RENDER_SCRIPT = """
from choicesignal.ui import render

render()
"""


def _imported_roots(path: Path) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
    return roots


def _widgets(app: AppTest) -> list:
    return [
        *app.radio, *app.selectbox, *app.multiselect, *app.checkbox, *app.button,
        *app.slider, *app.text_input, *app.number_input,
    ]


def _click(app: AppTest, key: str) -> None:
    next(button for button in app.button if button.key == key).click().run()
    assert not app.exception, [error.value for error in app.exception]


def test_ui_entry_point_matches_the_hub_contract() -> None:
    from choicesignal.ui import APP_INFO, render

    assert callable(render)
    assert APP_INFO == {"product": "Choice Signal", "version": __version__, "repo": "conjoint-analysis", "slug": "choice"}


def test_only_the_ui_package_imports_streamlit_or_plotly() -> None:
    offenders = {
        str(path.relative_to(PACKAGE)): sorted(_imported_roots(path) & UI_ONLY_LIBRARIES)
        for path in PACKAGE.rglob("*.py")
        if UI not in path.parents and _imported_roots(path) & UI_ONLY_LIBRARIES
    }
    assert not offenders, offenders


def test_core_package_imports_without_streamlit_or_plotly() -> None:
    # A fresh interpreter, so modules already imported by other tests cannot hide a stray import.
    code = (
        f"import sys\nsys.path.insert(0, {str(ROOT / 'src')!r})\n"
        "import choicesignal, choicesignal.concept_test, choicesignal.conjoint, choicesignal.errors, "
        "choicesignal.io\n"
        "loaded = sorted(name for name in ('streamlit', 'plotly') if name in sys.modules)\n"
        "assert not loaded, loaded\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr


def test_render_never_sets_page_config_or_navigation() -> None:
    for path in UI.glob("*.py"):
        if path.name == "signal_theme.py":
            continue
        source = path.read_text(encoding="utf-8")
        for call in ("st.set_page_config(", "st.navigation(", "st.Page("):
            assert call not in source, (path.name, call)


def test_bundled_demo_studies_match_the_examples() -> None:
    # The UI loads its demos from package data so they also work from a wheel (Signal Hub); keep them identical.
    for name in DEMOS:
        assert (UI / "assets" / "examples" / name).read_bytes() == (ROOT / "examples" / name).read_bytes(), name


def test_ui_reads_data_only_from_inside_the_package() -> None:
    # Signal Hub installs the app from its release zip as a normal package: repo-root folders such as examples/,
    # docs/ or assets/ do not exist there. Every file the UI reads must live under src/choicesignal/ and be
    # declared as package data.
    from choicesignal.ui import app as ui_app, signal_theme

    source = (UI / "app.py").read_text(encoding="utf-8")
    assert "parents[" not in source and ".parent.parent" not in source
    assert PACKAGE in ui_app.DEMOS.parents
    used = re.findall(r'load_demo\("([^"]+)"\)', source)
    assert sorted(used) == sorted(DEMOS)
    for name in used:
        assert (ui_app.DEMOS / name).is_file(), name
    assert PACKAGE in signal_theme.ASSETS.parents
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert '"choicesignal.ui" = ["assets/marks/*", "assets/examples/*.csv"]' in pyproject


def test_render_runs_from_a_script_without_set_page_config() -> None:
    app = AppTest.from_string(RENDER_SCRIPT, default_timeout=120)
    app.run()

    assert not app.exception, [error.value for error in app.exception]
    assert app.sidebar.radio[0].key == "choice:page"
    assert "choice:tables" in app.session_state
    assert "tables" not in app.session_state
    body = "\n".join(str(item.value) for item in app.markdown)
    assert "CONJOINT ANALYSIS, WITHOUT THE BLACK BOX" in body
    assert f"Choice Signal v{__version__}" in body

    _click(app, "choice:demo_coffee")
    assert app.sidebar.radio[0].value == "1 · Data & design"
    assert any(metric.label == "Rows (ratings)" and metric.value == "4,200" for metric in app.metric)


@pytest.mark.parametrize("page", PAGES)
def test_every_widget_key_is_namespaced(page: str) -> None:
    app = AppTest.from_string(RENDER_SCRIPT, default_timeout=120)
    app.run()
    _click(app, "choice:demo_coffee")
    app.sidebar.radio[0].set_value(page).run()

    assert not app.exception, [error.value for error in app.exception]
    widgets = _widgets(app)
    assert widgets
    unkeyed = [(type(widget).__name__, widget.label) for widget in widgets if widget.key is None]
    assert not unkeyed, unkeyed
    assert all(widget.key.startswith("choice:") for widget in widgets)


def test_simulator_and_concept_widgets_are_namespaced() -> None:
    app = AppTest.from_string(RENDER_SCRIPT, default_timeout=180)
    app.run()
    _click(app, "choice:demo_coffee")
    _click(app, "choice:save_design")
    app.sidebar.radio[0].set_value("2 · Utilities & importance").run()
    _click(app, "choice:estimate")
    app.sidebar.radio[0].set_value("3 · Simulate & export").run()
    _click(app, "choice:simulate")
    assert app.session_state["choice:shares"] is not None
    simulator_widgets = _widgets(app)

    _click(app, "choice:demo_concept")
    _click(app, "choice:run_concept")
    assert app.session_state["choice:concept"]["data"].n == 260
    concept_widgets = _widgets(app)

    for widgets in (simulator_widgets, concept_widgets):
        assert all(widget.key and widget.key.startswith("choice:") for widget in widgets), [
            (type(widget).__name__, widget.label, widget.key) for widget in widgets
        ]
    assert all(key.startswith("choice:") for key in app.session_state), list(app.session_state)


def test_session_state_and_widget_keys_go_through_the_namespace_helper() -> None:
    source = (UI / "app.py").read_text(encoding="utf-8")
    state_keys = re.findall(r"session_state(?:\[|\.get\(|\.pop\(|\.setdefault\()\s*([^,\])]+)", source)
    widget_keys = re.findall(r"\bkey=([^,)\n]+)", source)
    assert state_keys and widget_keys
    assert all(key.startswith("k(") for key in state_keys), state_keys
    assert all(key.startswith("k(") for key in widget_keys), widget_keys
    assert 'NS = "choice"' in source
