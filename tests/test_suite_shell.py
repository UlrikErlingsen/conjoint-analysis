from pathlib import Path

from streamlit.testing.v1 import AppTest

from choicesignal import __version__


ROOT = Path(__file__).parents[1]
APP = str(ROOT / "app.py")
UI = ROOT / "src" / "choicesignal" / "ui"


def test_shared_signal_shell_renders() -> None:
    app = AppTest.from_file(APP, default_timeout=120)
    app.run()

    assert not app.exception, [error.value for error in app.exception]
    body = "\n".join(str(item.value) for item in app.markdown)
    sidebar = "\n".join(str(item.value) for item in app.sidebar.markdown)
    assert "OPEN CONJOINT ANALYSIS" in body
    assert "CONJOINT ANALYSIS, WITHOUT THE BLACK BOX" in body
    assert "Treat these results as decision support, not predicted market shares." in body
    assert f"Choice Signal v{__version__}" in body
    assert "Stated preference, not market share" in body
    assert "Part of the Signal suite" in body
    assert "AGPL-3.0-or-later" in body
    assert "sg-mast" in body  # the shared Signal masthead
    assert "sg-foot" in body  # the shared Signal footer
    assert "Know what customers actually value." in sidebar
    assert "sg-side" in sidebar  # the shared Signal sidebar lockup


def test_app_uses_shared_signal_theme_instead_of_pasted_styles() -> None:
    standalone = (ROOT / "app.py").read_text(encoding="utf-8")
    ui_source = (UI / "app.py").read_text(encoding="utf-8")
    theme = (UI / "signal_theme.py").read_text(encoding="utf-8")
    assert 'st.set_page_config(**sig.page_config("choice"))' in standalone
    assert "sig.apply(NS)" in ui_source
    assert "<style>" not in standalone + ui_source
    for old_colour in ("#173c3a", "#d95b40", "#83d2b4", "#f2c66d", "#17322e", "#102c2a", "#f8f5ed", "#9b3e2b"):
        assert old_colour not in (standalone + ui_source).lower()
    # Every Plotly figure gets the per-app template and is shown through sig.chart (theme=None).
    assert ui_source.count("px.bar(") == ui_source.count("template=sig.template(NS)")
    assert ui_source.count("px.bar(") == ui_source.count("sig.chart(NS, ")
    assert "st.plotly_chart" not in ui_source
    assert "ChoiceSignal" not in ui_source.replace("choicesignal", "")
    assert (UI / "assets" / "marks" / "choicesignal-mark-64.png").exists()
    assert ":focus-visible" in theme
    assert "friendly_message" in ui_source


def test_runtime_scaffolding_is_private_and_health_checked() -> None:
    config = (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    launcher = (ROOT / "run_app.command").read_text(encoding="utf-8")
    windows_launcher = (ROOT / "run_app.bat").read_text(encoding="utf-8")

    assert "gatherUsageStats = false" in config
    assert 'base = "light"' in config
    assert 'primaryColor = "#a06f1f"' in config  # Signal Research family, 600 step
    assert "USER choicesignal" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert "--server.maxUploadSize=200" in dockerfile  # the documented local limit, above the synced config default
    assert "--browser.gatherUsageStats=false" in launcher
    assert "--browser.gatherUsageStats=false" in windows_launcher
    assert "CHOICESIGNAL_PORT" in launcher
