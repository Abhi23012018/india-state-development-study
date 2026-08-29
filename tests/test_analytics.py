import pandas as pd

from src.analytics import correlation_matrices, fit_income_ols


def _data():
    return pd.DataFrame({
        "State GSDP": range(10, 30),
        "Per Capita Income": range(100, 300, 10),
        "Literacy Rate": range(60, 80),
        "Population Density": range(200, 400, 10),
    })


def test_correlations_include_both_methods():
    result = correlation_matrices(_data())
    assert set(result) == {"pearson", "spearman"}
    assert result["pearson"].shape == (4, 4)


def test_ols_uses_expected_predictors():
    model = fit_income_ols(_data())
    assert set(model.params.index) == {"const", "Literacy Rate", "Population Density"}

