from pathlib import Path

import pandas as pd
import pytest

from choicesignal.errors import DataProblem
from choicesignal.io import load_data, results_to_excel, results_to_json, safe_for_spreadsheet


ROOT = Path(__file__).parents[1]


def test_demo_files_load_with_expected_shape():
    coffee = load_data(ROOT / "examples" / "demo_coffee_ratings.csv")
    frame = coffee.tables["ratings"]
    assert list(frame.columns) == ["respondent_id", "brand", "price_per_month", "beans", "delivery", "rating"]
    assert frame["respondent_id"].nunique() == 300
    cars = load_data(ROOT / "examples" / "demo_car_ratings.csv").tables["ratings"]
    assert cars["respondent_id"].nunique() == 350
    assert list(cars.columns) == ["respondent_id", "brand_origin", "body_type", "engine", "price", "rating"]
    streaming = load_data(ROOT / "examples" / "demo_streaming_ratings.csv").tables["ratings"]
    assert streaming["respondent_id"].nunique() == 150


def test_unsupported_extension_is_rejected():
    with pytest.raises(DataProblem, match="file types"):
        load_data(b"a,b\n1,2", name="ratings.txt")


def test_excel_and_json_exports_round_trip():
    frame = pd.DataFrame({"attribute": ["price"], "level": ["=cmd()"], "partworth": [1.5]})
    workbook = results_to_excel({"Partworths": frame})
    assert workbook[:2] == b"PK"
    payload = results_to_json({"partworths": frame}, {"product": "ChoiceSignal"})
    assert b"partworths" in payload
    neutralized = safe_for_spreadsheet(frame)
    assert neutralized["level"].iloc[0].startswith("'")
