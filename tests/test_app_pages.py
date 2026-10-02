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


UPLOAD_SCRIPT = """
import io
from pathlib import Path

import streamlit as st

from choicesignal.ui import render


class FakeUpload(io.BytesIO):
    name = "my_study.csv"
    file_id = "upload-1"
    size = 0


def fake_uploader(*args, **kwargs):
    data = (Path(r"{demos}") / "demo_car_ratings.csv").read_bytes()
    upload = FakeUpload(data)
    upload.size = len(data)
    return upload


original = st.file_uploader
if st.session_state.get("test:upload"):
    st.file_uploader = fake_uploader
try:
    render()
finally:
    st.file_uploader = original
"""


@pytest.mark.parametrize("page", PAGES)
def test_every_page_renders_on_first_run(page):
    app = AppTest.from_file(APP, default_timeout=30)
    app.run()
    app.sidebar.radio[0].set_value(page).run()
    assert not app.exception, [error.value for error in app.exception]


def test_first_run_preloads_the_fictional_coffee_demo():
    app = AppTest.from_file(APP, default_timeout=30)
    app.run()
    assert not app.exception, [error.value for error in app.exception]
    assert app.sidebar.radio[0].value == "Welcome"
    assert app.session_state["choice:active_demo"] == "demo_coffee_ratings.csv"
    assert app.session_state["choice:source_name"] == "demo_coffee_ratings.csv"
    assert any("fictional coffee-subscription demo is already loaded" in block.value for block in app.markdown)
    assert any("demo_coffee_ratings.csv" in caption.value for caption in app.sidebar.caption)
    app.sidebar.radio[0].set_value("1 · Data & design").run()
    assert any(metric.label == "Rows (ratings)" and metric.value == "4,200" for metric in app.metric)
    assert not app.exception, [error.value for error in app.exception]


def test_clearing_the_preloaded_demo_leaves_the_session_empty():
    app = AppTest.from_file(APP, default_timeout=30)
    app.run()
    next(button for button in app.sidebar.button if button.label == "Clear session data").click().run()
    assert not app.exception, [error.value for error in app.exception]
    assert app.session_state["choice:tables"] is None
    app.sidebar.radio[0].set_value("1 · Data & design").run()
    assert not any(metric.label == "Rows (ratings)" for metric in app.metric)
    assert not any("already loaded" in block.value for block in app.markdown)


def test_an_upload_replaces_the_preloaded_demo():
    demos = Path(__file__).parents[1] / "src" / "choicesignal" / "ui" / "assets" / "examples"
    app = AppTest.from_string(UPLOAD_SCRIPT.replace("{demos}", str(demos)), default_timeout=30)
    app.run()
    assert app.session_state["choice:active_demo"] == "demo_coffee_ratings.csv"
    app.session_state["test:upload"] = True
    app.run()
    assert not app.exception, [error.value for error in app.exception]
    assert app.session_state["choice:source_name"] == "my_study.csv"
    assert "choice:active_demo" not in app.session_state
    assert app.sidebar.radio[0].value == "1 · Data & design"
    assert any(metric.label == "Rows (ratings)" and metric.value == "5,600" for metric in app.metric)


def test_loading_a_demo_navigates_to_page_one_and_keeps_the_radio_in_sync():
    app = AppTest.from_file(APP, default_timeout=30)
    app.run()
    next(button for button in app.sidebar.button if button.label == "Demo · coffee subscriptions").click().run()
    assert app.sidebar.radio[0].value == "1 · Data & design"
    assert app.session_state["choice:nav_target"] == "1 · Data & design"
    assert any(metric.label == "Rows (ratings)" and metric.value == "4,200" for metric in app.metric)
    assert not app.exception, [error.value for error in app.exception]


def test_concept_demo_flow_reaches_results():
    app = AppTest.from_file(APP, default_timeout=30)
    app.run()
    next(button for button in app.sidebar.button if button.label == "Demo · concept test").click().run()
    assert app.sidebar.radio[0].value == "4 · Concept test"
    next(button for button in app.button if button.label == "Run the concept test").click().run()
    assert not app.exception, [error.value for error in app.exception]
    assert app.session_state["choice:concept"] is not None
    assert app.session_state["choice:concept"]["data"].n == 260
    assert any(metric.label == "Top two boxes" for metric in app.metric)


def test_full_flow_reaches_estimates():
    app = AppTest.from_file(APP, default_timeout=60)
    app.run()
    next(button for button in app.sidebar.button if button.label == "Demo · coffee subscriptions").click().run()
    next(button for button in app.button if button.label == "Check the design and save the setup").click().run()
    assert app.session_state["choice:study"] is not None
    app.sidebar.radio[0].set_value("2 · Utilities & importance").run()
    next(button for button in app.button if button.label == "Estimate part-worth utilities").click().run()
    assert not app.exception, [error.value for error in app.exception]
    result = app.session_state["choice:result"]
    assert result.method == "individual"
    assert result.importance.iloc[0]["attribute"] == "price_per_month"
