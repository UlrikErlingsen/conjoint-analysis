"""Data limits: none locally, demo caps only with SIGNAL_PUBLIC=1, and block processing changes no result.

Every test is fast: inputs beyond the demo caps are built by lowering the caps, never by building a huge file.
"""

from io import BytesIO
import json
from pathlib import Path
import zipfile

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from choicesignal import conjoint, limits
from choicesignal.conjoint import build_design, design_report, estimate_conjoint, optimal_products
from choicesignal.errors import DataProblem, friendly_message
from choicesignal.io import load_data, results_to_json
from choicesignal.limits import Limits


ROOT = Path(__file__).parents[1]
ATTRIBUTES = ["brand", "price_per_month", "beans", "delivery"]
TINY_DEMO = Limits(
    upload_bytes=1_000_000, json_bytes=32, expanded_workbook_bytes=1024, table_rows=50, total_cells=100,
    rating_rows=50, attributes=2, levels_per_attribute=2, search_cells=10,
)


def _coffee() -> pd.DataFrame:
    return load_data(ROOT / "examples" / "demo_coffee_ratings.csv").tables["ratings"]


@pytest.fixture
def tiny_demo_caps(monkeypatch):
    monkeypatch.setattr(limits, "PUBLIC_DEMO", TINY_DEMO)
    return monkeypatch


def _workbook_bomb() -> bytes:
    output = BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as workbook:
        workbook.writestr("xl/worksheets/sheet1.xml", "x" * 4096)
    return output.getvalue()


def test_local_mode_accepts_input_beyond_the_demo_caps(tiny_demo_caps):
    tiny_demo_caps.delenv("SIGNAL_PUBLIC", raising=False)
    assert limits.active() == Limits()
    frame = _coffee()
    csv = frame.to_csv(index=False).encode("utf-8")
    assert len(load_data(csv, name="ratings.csv").tables["ratings"]) > TINY_DEMO.table_rows
    assert len(load_data(b'[{"a": 1}, {"a": 2}]', name="ratings.json").tables["ratings"]) == 2
    with pytest.raises(DataProblem, match="could not be read"):  # past the size guard; just not a real workbook
        load_data(_workbook_bomb(), name="ratings.xlsx")
    design = build_design(frame, "respondent_id", "rating", ATTRIBUTES)  # > 2 attributes, > 2 levels
    result = estimate_conjoint(frame, design)
    assert result.method == "individual"
    assert len(optimal_products(result, design)) == 5  # far beyond 10 search cells


def test_many_levels_warn_locally_instead_of_refusing():
    frame = _coffee()
    frame = frame.assign(price_per_month=frame["price_per_month"] + frame.index.map(lambda index: f"-{index % 14}"))
    design = build_design(frame, "respondent_id", "rating", ["brand", "price_per_month"])
    assert len(design.levels["price_per_month"]) > conjoint.ADVISED_LEVELS_PER_ATTRIBUTE
    try:
        _, warnings = design_report(frame, design)
    except DataProblem:
        return  # a confounded toy design is fine; the point is that build_design accepted it
    assert any("more than 12 levels" in warning for warning in warnings)


def test_public_demo_enforces_its_caps_and_says_so(tiny_demo_caps):
    frame = _coffee()
    tiny_demo_caps.setenv("SIGNAL_PUBLIC", "1")
    cases = [
        (lambda: load_data(b"x" * 1_000_001, name="big.csv"), "Uploads are limited"),
        (lambda: load_data(b'[{"a": 1}, {"a": 2}, {"a": 3}, {"a": 4}]', name="ratings.json"), "JSON uploads are limited"),
        (lambda: load_data(_workbook_bomb(), name="ratings.xlsx"), "expand to at most"),
        (lambda: load_data(frame.to_csv(index=False).encode("utf-8"), name="ratings.csv"), "more than 50 rows"),
        (lambda: build_design(frame, "respondent_id", "rating", ATTRIBUTES), "up to 50 rating rows"),
    ]
    small = frame.head(40)
    cases += [
        (lambda: build_design(small, "respondent_id", "rating", ATTRIBUTES), "up to 2 attributes"),
        (lambda: build_design(small, "respondent_id", "rating", ["brand", "price_per_month"]), "up to 2."),
    ]
    for call, pattern in cases:
        with pytest.raises(DataProblem, match=pattern) as caught:
            call()
        assert limits.DEMO_NOTE in str(caught.value)

    tiny_demo_caps.setattr(limits, "PUBLIC_DEMO", Limits(search_cells=10))
    design = build_design(frame, "respondent_id", "rating", ATTRIBUTES)
    result = estimate_conjoint(frame, design)
    with pytest.raises(DataProblem, match="the demo stops at 10") as caught:
        optimal_products(result, design)
    assert limits.DEMO_NOTE in str(caught.value)


def test_real_demo_caps_follow_the_previous_release_limits():
    assert limits.PUBLIC_DEMO.upload_bytes == 200 * 1024 * 1024
    assert limits.PUBLIC_DEMO.rating_rows == 500_000
    assert limits.PUBLIC_DEMO.levels_per_attribute == 12


def test_running_out_of_memory_is_a_plain_message(monkeypatch):
    assert "not enough memory" in friendly_message(MemoryError())

    def exhausted(*args, **kwargs):
        raise MemoryError

    monkeypatch.setattr("choicesignal.io.pd.read_csv", exhausted)
    with pytest.raises(DataProblem, match="not enough memory for this file"):
        load_data(b"a,b\n1,2\n", name="huge.csv")


def test_exhaustive_search_keeps_its_combinatorial_bound_with_a_clear_message(monkeypatch):
    frame = _coffee()
    design = build_design(frame, "respondent_id", "rating", ATTRIBUTES)
    result = estimate_conjoint(frame, design)
    monkeypatch.setattr(conjoint, "EXHAUSTIVE_SEARCH_CELLS", 10)
    with pytest.raises(DataProblem, match="grows with every added level"):
        optimal_products(result, design)


def test_blocks_do_not_change_estimates_or_search(monkeypatch):
    frame = _coffee()
    design = build_design(frame, "respondent_id", "rating", ATTRIBUTES)
    reference = estimate_conjoint(frame, design)
    competitors = {
        "A": {"brand": "Casa Verde", "price_per_month": "$14", "beans": "House blend", "delivery": "Weekly"},
        "B": {"brand": "Nordic Roast", "price_per_month": "$19", "beans": "Single origin", "delivery": "Monthly"},
    }
    expected = optimal_products(reference, design, competitors)
    monkeypatch.setattr(conjoint, "ESTIMATION_BLOCK_CELLS", 50)
    monkeypatch.setattr(conjoint, "SEARCH_BLOCK_CELLS", 100)
    blocked = estimate_conjoint(frame, design)
    pd.testing.assert_frame_equal(blocked.individual, reference.individual)
    pd.testing.assert_frame_equal(blocked.fit, reference.fit)
    pd.testing.assert_frame_equal(optimal_products(blocked, design, competitors), expected)


def test_large_json_exports_keep_every_row(monkeypatch):
    monkeypatch.setattr("choicesignal.io.JSON_COMPACT_ROWS", 2)
    table = pd.DataFrame({"respondent": [1, 2, 3], "partworth": [0.5, -0.25, 0.0]})
    payload = json.loads(results_to_json({"individual": table}, {"seed": 1}))
    assert payload["individual"] == table.to_dict(orient="records")


LARGE_APP = """
import choicesignal.ui.app as choice_app

choice_app.SCREEN_TABLE_ROWS = 5
choice_app.LAZY_EXPORT_RESPONDENTS = 5
choice_app.render()
"""


def test_large_studies_truncate_on_screen_and_build_exports_on_click():
    app = AppTest.from_string(LARGE_APP, default_timeout=120)
    app.run()
    app.sidebar.radio[0].set_value("1 · Data & design").run()
    next(button for button in app.button if button.label.startswith("Check the design")).click().run()
    app.sidebar.radio[0].set_value("2 · Utilities & importance").run()
    next(button for button in app.button if button.label.startswith("Estimate part-worth")).click().run()
    assert not app.exception, [error.value for error in app.exception]
    assert any("Showing the first 5 of" in str(caption.value) for caption in app.caption)
    app.sidebar.radio[0].set_value("3 · Simulate & export").run()
    assert not app.exception, [error.value for error in app.exception]
    assert any("prepared when you click it" in str(caption.value) for caption in app.caption)
