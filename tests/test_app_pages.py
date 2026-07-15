from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest


APP = str(Path(__file__).parents[1] / "app.py")
PAGES = [
    "Welcome",
    "1 · Data & design",
    "2 · Utilities & importance",
    "3 · Simulate & export",
    "4 · Concept test",
    "Methods & limits",
]


@pytest.mark.parametrize("page", PAGES)
def test_every_page_renders_without_data(page):
    app = AppTest.from_file(APP, default_timeout=30)
    app.run()
    app.sidebar.radio[0].set_value(page).run()
    assert not app.exception, [error.value for error in app.exception]


def test_loading_a_demo_navigates_to_page_one_and_keeps_the_radio_in_sync():
    app = AppTest.from_file(APP, default_timeout=30)
    app.run()
    next(button for button in app.sidebar.button if button.label == "Demo · coffee subscriptions").click().run()
    assert app.sidebar.radio[0].value == "1 · Data & design"
    assert app.session_state["nav_target"] == "1 · Data & design"
    assert any(metric.label == "Rows (ratings)" and metric.value == "4,200" for metric in app.metric)
    assert not app.exception, [error.value for error in app.exception]


def test_concept_demo_flow_reaches_results():
    app = AppTest.from_file(APP, default_timeout=30)
    app.run()
    next(button for button in app.sidebar.button if button.label == "Demo · concept test").click().run()
    assert app.sidebar.radio[0].value == "4 · Concept test"
    next(button for button in app.button if button.label == "Run the concept test").click().run()
    assert not app.exception, [error.value for error in app.exception]
    assert app.session_state["concept"] is not None
    assert app.session_state["concept"]["data"].n == 260
    assert any(metric.label == "Top two boxes" for metric in app.metric)


def test_full_flow_reaches_estimates():
    app = AppTest.from_file(APP, default_timeout=60)
    app.run()
    next(button for button in app.sidebar.button if button.label == "Demo · coffee subscriptions").click().run()
    next(button for button in app.button if button.label == "Check the design and save the setup").click().run()
    assert app.session_state["study"] is not None
    app.sidebar.radio[0].set_value("2 · Utilities & importance").run()
    next(button for button in app.button if button.label == "Estimate part-worth utilities").click().run()
    assert not app.exception, [error.value for error in app.exception]
    result = app.session_state["result"]
    assert result.method == "individual"
    assert result.importance.iloc[0]["attribute"] == "price_per_month"
