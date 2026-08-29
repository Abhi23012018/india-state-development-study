"""Download, validate, harmonize, and merge real India state indicators.

The pipeline uses public, versioned GitHub mirrors of Census 2011 and RBI/MoSPI
tables. Downloaded files are cached in ``data/raw`` for reproducible reruns.
No synthetic observations are generated.
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import re
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import numpy as np
import pandas as pd

LOGGER = logging.getLogger(__name__)
ROOT: Final = Path(__file__).resolve().parents[1]
RAW_DIR: Final = ROOT / "data" / "raw"
PROCESSED_DIR: Final = ROOT / "data" / "processed"


@dataclass(frozen=True)
class Source:
    """A remote CSV and its local cache name."""

    name: str
    url: str
    filename: str


SOURCES: Final = {
    "census": Source(
        "Census 2011 state indicators mirror",
        "https://gist.githubusercontent.com/NeeharikaGali/34a6bd81a0bbea3917c028179dbee34a/raw/population.csv",
        "census_2011_states.csv",
    ),
    "income": Source(
        "RBI state population and income mirror",
        "https://raw.githubusercontent.com/sahuvaibhav/Looker-Custom-Maps-Tutorial/master/RBI%20DATA%20states_wise_population_Income.csv",
        "rbi_state_income.csv",
    ),
    "gsdp": Source(
        "MoSPI/RBI state GSDP current-prices mirror",
        "https://raw.githubusercontent.com/pdp19/GDP_Analysis/master/Data_1A_for%20all%20state.csv",
        "state_gsdp_current_prices.csv",
    ),
}

STATE_ALIASES: Final = {
    "andaman & nicobar islands": "Andaman and Nicobar Islands",
    "andaman and nicobar islands": "Andaman and Nicobar Islands",
    "andhra pradesh": "Andhra Pradesh",
    "delhi": "Delhi",
    "nct of delhi": "Delhi",
    "national capital territory of delhi": "Delhi",
    "jammu & kashmir": "Jammu and Kashmir",
    "jammu and kashmir": "Jammu and Kashmir",
    "odisha": "Odisha",
    "orissa": "Odisha",
    "pondicherry": "Puducherry",
    "puducherry": "Puducherry",
    "uttaranchal": "Uttarakhand",
    "uttarakhand": "Uttarakhand",
    "west bengal1": "West Bengal",
}


def _state_key(value: object) -> str:
    text = re.sub(r"\s+", " ", str(value).strip()).lower()
    text = text.replace("&", "and")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


_NORMALIZED_ALIASES = {_state_key(k): v for k, v in STATE_ALIASES.items()}


def canonicalize_state(value: object) -> str:
    """Return a stable state/UT name while handling common source variants."""

    raw = re.sub(r"\s+", " ", str(value).strip())
    key = _state_key(raw)
    return _NORMALIZED_ALIASES.get(key, raw.title())


def _download(source: Source, raw_dir: Path, refresh: bool = False) -> Path:
    raw_dir.mkdir(parents=True, exist_ok=True)
    destination = raw_dir / source.filename
    if destination.exists() and destination.stat().st_size > 0 and not refresh:
        LOGGER.info("Using cached %s", destination)
        return destination

    LOGGER.info("Downloading %s", source.url)
    request = urllib.request.Request(
        source.url, headers={"User-Agent": "india-state-development-study/1.0"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        content = response.read()
    if len(content) < 100:
        raise ValueError(f"Downloaded file is unexpectedly small: {source.url}")
    destination.write_bytes(content)
    LOGGER.info("Cached %s (sha256=%s)", destination, hashlib.sha256(content).hexdigest())
    return destination


def _number(series: pd.Series) -> pd.Series:
    cleaned = series.astype("string").str.replace(",", "", regex=False).str.strip()
    cleaned = cleaned.replace({"NA": pd.NA, "N/A": pd.NA, "-": pd.NA, "": pd.NA})
    return pd.to_numeric(cleaned, errors="coerce")


def load_census(path: Path) -> pd.DataFrame:
    """Load state-level Census 2011 population, literacy, area, and density."""

    df = pd.read_csv(path, encoding="utf-8-sig")
    required = {"State", "Population", "Literacy Rate (%)", "Area (km*km)", "Density (1/km*km)"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Census source missing columns: {sorted(missing)}")
    out = df[list(required)].copy()
    out["State"] = out["State"].map(canonicalize_state)
    out = out.rename(
        columns={
            "Literacy Rate (%)": "Literacy Rate",
            "Area (km*km)": "Area Sq Km",
            "Density (1/km*km)": "Population Density",
        }
    )
    for column in ["Population", "Literacy Rate", "Area Sq Km", "Population Density"]:
        out[column] = _number(out[column])
    return out.drop_duplicates("State")


def load_income(path: Path) -> pd.DataFrame:
    """Load RBI-derived 2011-12 per-capita NSDP (income) by state."""

    df = pd.read_csv(path, encoding="utf-8-sig")
    required = {"States_Union Territories", "2011-12-INC"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Income source missing columns: {sorted(missing)}")
    out = df[list(required)].rename(
        columns={"States_Union Territories": "State", "2011-12-INC": "Per Capita Income"}
    )
    out["State"] = out["State"].map(canonicalize_state)
    out["Per Capita Income"] = _number(out["Per Capita Income"])
    return out.drop_duplicates("State")


def load_gsdp(path: Path) -> pd.DataFrame:
    """Reshape the wide 2011-12 current-price GSDP row to state records."""

    df = pd.read_csv(path, encoding="cp1252")
    item_col, year_col = "Items  Description", "Duration"
    if item_col not in df or year_col not in df:
        raise ValueError("GSDP source does not have the expected item/year columns")
    selected = df[
        df[item_col].astype(str).str.contains("GSDP - CURRENT PRICES", regex=False)
        & df[year_col].astype(str).str.strip().eq("2011-12")
    ]
    if len(selected) != 1:
        raise ValueError(f"Expected one 2011-12 GSDP row, found {len(selected)}")
    excluded = {item_col, year_col, "All_India GDP", "Average GDP state wise"}
    out = selected.drop(columns=[c for c in excluded if c in selected]).melt(
        var_name="State", value_name="State GSDP"
    )
    out["State"] = out["State"].map(canonicalize_state)
    out["State GSDP"] = _number(out["State GSDP"])
    return out.drop_duplicates("State")


def impute_historical_cells(df: pd.DataFrame) -> pd.DataFrame:
    """Fill numeric gaps deterministically: within-state ffill, then median.

    The forward-fill supports future multi-year inputs. In this cross-section it
    is intentionally a no-op; remaining cells use the cross-state median and are
    identified by ``Imputed Fields`` for auditability.
    """

    result = df.sort_values(["State", "Reference Year"]).copy()
    numeric = [
        "Population",
        "Literacy Rate",
        "Area Sq Km",
        "Population Density",
        "State GSDP",
        "Per Capita Income",
    ]
    missing_before = result[numeric].isna()
    result[numeric] = result.groupby("State", dropna=False)[numeric].ffill()
    for column in numeric:
        result[column] = result[column].fillna(result[column].median())
    result["Imputed Fields"] = missing_before.apply(
        lambda row: ", ".join(row.index[row].tolist()), axis=1
    )
    return result


def build_dataset(raw_dir: Path = RAW_DIR, processed_dir: Path = PROCESSED_DIR, refresh: bool = False) -> pd.DataFrame:
    """Build and persist the analysis-ready state cross-section."""

    paths = {key: _download(source, raw_dir, refresh) for key, source in SOURCES.items()}
    census = load_census(paths["census"])
    income = load_income(paths["income"])
    gsdp = load_gsdp(paths["gsdp"])

    merged = census.merge(income, on="State", how="inner", validate="one_to_one")
    merged = merged.merge(gsdp, on="State", how="inner", validate="one_to_one")
    merged["Reference Year"] = "2011-12"
    merged = impute_historical_cells(merged)
    # One crore rupees = 10,000,000 rupees. This is gross output per Census resident.
    merged["Per Capita GSDP"] = merged["State GSDP"] * 10_000_000 / merged["Population"]
    merged["State GSDP"] = merged["State GSDP"].astype(float)  # INR crore

    if merged.empty or len(merged) < 20:
        raise ValueError(f"Merge yielded only {len(merged)} states/UTs; source alignment likely failed")
    if merged["State"].duplicated().any():
        raise ValueError("Duplicate canonical state names remain after merge")
    if not merged["Literacy Rate"].between(0, 100).all():
        raise ValueError("Literacy rates must lie between 0 and 100")
    if (merged[["Population", "Population Density", "State GSDP", "Per Capita Income"]] <= 0).any().any():
        raise ValueError("Core demographic/economic measures must be positive")

    columns = [
        "State", "Reference Year", "Population", "Area Sq Km", "Population Density",
        "Literacy Rate", "State GSDP", "Per Capita Income", "Per Capita GSDP", "Imputed Fields",
    ]
    result = merged[columns].sort_values("State").reset_index(drop=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    output = processed_dir / "india_state_development.csv"
    result.to_csv(output, index=False, float_format="%.4f")
    LOGGER.info("Wrote %d rows to %s", len(result), output)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Redownload cached source files")
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    parser.add_argument("--processed-dir", type=Path, default=PROCESSED_DIR)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    data = build_dataset(args.raw_dir, args.processed_dir, args.refresh)
    print(data.to_string(index=False))


if __name__ == "__main__":
    main()
