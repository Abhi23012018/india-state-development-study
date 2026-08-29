import json
from pathlib import Path

import pandas as pd
import pytest

from src.map_visualization import (
    METRICS,
    build_figure,
    canonicalize_state,
    load_geojson,
    prepare_map_data,
)


def _geojson(feature_names):
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"state_name": name, "state_name_harmonized": name},
                "geometry": {"type": "Polygon", "coordinates": []},
            }
            for name in feature_names
        ],
    }


def test_required_aliases_are_harmonized():
    expected = {
        "Orissa": "Odisha",
        "Pondicherry": "Puducherry",
        "NCT of Delhi": "Delhi",
        "Jammu & Kashmir": "Jammu and Kashmir",
        "Andaman & Nicobar Islands": "Andaman and Nicobar Islands",
    }
    assert {name: canonicalize_state(name) for name in expected} == expected


def test_load_geojson_rejects_post_2011_boundary_model(tmp_path: Path):
    names = [f"State {i}" for i in range(33)] + ["Telangana", "Ladakh"]
    path = tmp_path / "states.geojson"
    path.write_text(json.dumps(_geojson(names)), encoding="utf-8")
    with pytest.raises(ValueError, match="Census 2011"):
        load_geojson(path)


def test_all_geographies_remain_visible_when_data_is_missing():
    geo = _geojson(["Odisha", "Puducherry", "Lakshadweep"])
    for feature in geo["features"]:
        feature["properties"]["state_key"] = canonicalize_state(
            feature["properties"]["state_name_harmonized"]
        )
    data = pd.DataFrame(
        [
            {
                "State": "Orissa",
                "Literacy Rate": 73.0,
                "Population Density": 270,
                "Population": 42_000_000,
                "Per Capita Income": 43_000,
            },
            {
                "State": "Pondicherry",
                "Literacy Rate": 86.0,
                "Population Density": 2600,
                "Population": 1_250_000,
                "Per Capita Income": 103_000,
            },
        ]
    )
    merged = prepare_map_data(data, geo)
    assert len(merged) == 3
    assert merged.loc[merged["State"] == "Lakshadweep", "Data Status"].item() == "No project observation"
    figure = build_figure(merged, geo)
    assert len(figure["data"][0]["locations"]) == 3
    assert len(figure["layout"]["updatemenus"][0]["buttons"]) == len(METRICS)

