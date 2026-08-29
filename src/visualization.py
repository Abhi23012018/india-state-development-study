"""Publication-ready static visualizations for the study."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

try:
    from .analytics import ANALYSIS_COLUMNS, correlation_matrices
except ImportError:  # Supports direct execution: python src/visualization.py
    from analytics import ANALYSIS_COLUMNS, correlation_matrices

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "processed" / "india_state_development.csv"
DEFAULT_OUTPUT = ROOT / "outputs"


def save_correlation_heatmap(df: pd.DataFrame, output_path: Path, method: str = "pearson") -> None:
    matrices = correlation_matrices(df)
    if method not in matrices:
        raise ValueError(f"Unknown correlation method: {method}")
    sns.set_theme(style="whitegrid", context="talk")
    fig, ax = plt.subplots(figsize=(10, 8))
    sns.heatmap(
        matrices[method], annot=True, fmt=".2f", cmap="vlag", center=0,
        vmin=-1, vmax=1, square=True, linewidths=0.6, ax=ax,
        cbar_kws={"label": f"{method.title()} correlation"},
    )
    ax.set_title(f"India State Development Indicators: {method.title()} Correlations", pad=18)
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def save_income_literacy_bubble_plot(df: pd.DataFrame, output_path: Path) -> None:
    required = {"Literacy Rate", "Per Capita Income", "Population", "State"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Dataset missing plot columns: {sorted(missing)}")
    plot = df[list(required)].dropna().copy()
    population_millions = plot["Population"] / 1_000_000
    sizes = 60 + 740 * population_millions / population_millions.max()

    sns.set_theme(style="whitegrid", context="talk")
    fig, ax = plt.subplots(figsize=(13, 9))
    sns.regplot(
        data=plot, x="Literacy Rate", y="Per Capita Income", scatter=False,
        ci=95, color="#c44e52", line_kws={"linewidth": 2.2}, ax=ax,
    )
    scatter = ax.scatter(
        plot["Literacy Rate"], plot["Per Capita Income"], s=sizes,
        c=population_millions, cmap="viridis", alpha=0.72,
        edgecolor="white", linewidth=0.8,
    )
    for _, row in plot.nlargest(5, "Population").iterrows():
        ax.annotate(row["State"], (row["Literacy Rate"], row["Per Capita Income"]),
                    xytext=(5, 5), textcoords="offset points", fontsize=9)
    colorbar = fig.colorbar(scatter, ax=ax, pad=0.02)
    colorbar.set_label("Census 2011 population (millions)")
    ax.set(
        title="Literacy and Per-Capita Income Across Indian States/UTs",
        xlabel="Census 2011 literacy rate (%)",
        ylabel="Per-capita NSDP / income, 2011–12 (INR)",
    )
    ax.ticklabel_format(style="plain", axis="y")
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def generate_visualizations(input_path: Path = DEFAULT_INPUT, output_dir: Path = DEFAULT_OUTPUT) -> None:
    df = pd.read_csv(input_path)
    # Assert columns here for a clearer failure before rendering.
    if set(ANALYSIS_COLUMNS).difference(df.columns):
        raise ValueError("Processed input does not contain all analysis columns")
    save_correlation_heatmap(df, output_dir / "correlation_heatmap.png")
    save_income_literacy_bubble_plot(df, output_dir / "literacy_income_bubble.png")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    generate_visualizations(args.input, args.output_dir)


if __name__ == "__main__":
    main()

