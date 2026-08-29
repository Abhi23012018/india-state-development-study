"""Correlation and regression analysis for the state development dataset."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import statsmodels.api as sm
from statsmodels.regression.linear_model import RegressionResultsWrapper

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "processed" / "india_state_development.csv"
DEFAULT_OUTPUT = ROOT / "outputs"
ANALYSIS_COLUMNS = ["State GSDP", "Per Capita Income", "Literacy Rate", "Population Density"]


def correlation_matrices(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Return pairwise-complete Pearson and Spearman correlation matrices."""

    missing = set(ANALYSIS_COLUMNS).difference(df.columns)
    if missing:
        raise ValueError(f"Dataset missing analysis columns: {sorted(missing)}")
    values = df[ANALYSIS_COLUMNS].apply(pd.to_numeric, errors="coerce")
    return {
        "pearson": values.corr(method="pearson", min_periods=3),
        "spearman": values.corr(method="spearman", min_periods=3),
    }


def fit_income_ols(df: pd.DataFrame) -> RegressionResultsWrapper:
    """Fit OLS: per-capita income ~ literacy rate + population density.

    HC3 heteroskedasticity-robust standard errors are used because state-level
    cross-sections commonly exhibit non-constant residual variance.
    """

    columns = ["Per Capita Income", "Literacy Rate", "Population Density"]
    clean = df[columns].apply(pd.to_numeric, errors="coerce").dropna()
    if len(clean) < 10:
        raise ValueError("At least 10 complete observations are required for OLS")
    y = clean["Per Capita Income"]
    x = sm.add_constant(clean[["Literacy Rate", "Population Density"]], has_constant="add")
    return sm.OLS(y, x).fit(cov_type="HC3")


def run_analysis(input_path: Path = DEFAULT_INPUT, output_dir: Path = DEFAULT_OUTPUT) -> None:
    df = pd.read_csv(input_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    for method, matrix in correlation_matrices(df).items():
        matrix.to_csv(output_dir / f"correlation_{method}.csv", float_format="%.4f")
    model = fit_income_ols(df)
    (output_dir / "ols_summary.txt").write_text(model.summary().as_text(), encoding="utf-8")
    coefficients = pd.DataFrame(
        {"coefficient": model.params, "std_error_hc3": model.bse, "p_value": model.pvalues}
    )
    coefficients.to_csv(output_dir / "ols_coefficients.csv", float_format="%.6f")
    print(model.summary())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    run_analysis(args.input, args.output_dir)


if __name__ == "__main__":
    main()

