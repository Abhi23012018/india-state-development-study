from pathlib import Path

import pandas as pd

from src.data_pipeline import canonicalize_state, load_gsdp, impute_historical_cells


def test_canonicalize_common_state_variants():
    assert canonicalize_state("NCT of Delhi") == "Delhi"
    assert canonicalize_state("Jammu & Kashmir") == "Jammu and Kashmir"
    assert canonicalize_state("Orissa") == "Odisha"
    assert canonicalize_state("West Bengal1") == "West Bengal"


def test_load_gsdp_chooses_2011_12(tmp_path: Path):
    source = tmp_path / "gsdp.csv"
    source.write_text(
        "Items  Description,Duration,NCT of Delhi,All_India GDP,Average GDP state wise\n"
        "GSDP - CURRENT PRICES (` in Crore),2011-12,343767,10,5\n"
        "GSDP - CURRENT PRICES (` in Crore),2012-13,391238,11,6\n",
        encoding="cp1252",
    )
    result = load_gsdp(source)
    assert result.to_dict("records") == [{"State": "Delhi", "State GSDP": 343767}]


def test_imputation_is_auditable():
    row = {
        "State": "Example", "Reference Year": "2011-12", "Population": 1,
        "Literacy Rate": None, "Area Sq Km": 1, "Population Density": 1,
        "State GSDP": 1, "Per Capita Income": 1,
    }
    peer = dict(row, State="Peer", **{"Literacy Rate": 80})
    result = impute_historical_cells(pd.DataFrame([row, peer]))
    example = result.loc[result["State"] == "Example"].iloc[0]
    assert example["Literacy Rate"] == 80
    assert "Literacy Rate" in example["Imputed Fields"]

