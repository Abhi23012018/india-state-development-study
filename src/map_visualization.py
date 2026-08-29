"""Generate an interactive Census 2011 India state choropleth.

The map reads only the analysis-ready project dataset. Geographic boundaries
are downloaded from the ``saketlab/censusindia`` Census 2011 state GeoJSON and
cached locally. No observations are synthesized for unmatched territories.
"""

from __future__ import annotations

import argparse
import json
import logging
import urllib.request
from pathlib import Path
from typing import Any, Final

import pandas as pd

LOGGER = logging.getLogger(__name__)
ROOT: Final = Path(__file__).resolve().parents[1]
DEFAULT_INPUT: Final = ROOT / "data" / "processed" / "india_state_development.csv"
DEFAULT_GEOJSON: Final = ROOT / "data" / "raw" / "india-census-2011-states.geojson"
DEFAULT_HTML: Final = ROOT / "outputs" / "india_state_choropleth.html"
DEFAULT_PNG: Final = ROOT / "outputs" / "india_state_choropleth.png"
GEOJSON_URL: Final = (
    "https://raw.githubusercontent.com/saketlab/censusindia/master/inst/extdata/"
    "india-census-2011-states.geojson"
)

STATE_ALIASES: Final = {
    "orissa": "Odisha",
    "pondicherry": "Puducherry",
    "nct of delhi": "Delhi",
    "delhi nct": "Delhi",
    "jammu & kashmir": "Jammu and Kashmir",
    "jammu and kashmir": "Jammu and Kashmir",
    "andaman & nicobar island": "Andaman and Nicobar Islands",
    "andaman & nicobar islands": "Andaman and Nicobar Islands",
    "andaman and nicobar islands": "Andaman and Nicobar Islands",
    "dadara & nagar havelli": "Dadra and Nagar Haveli",
    "dadra & nagar haveli": "Dadra and Nagar Haveli",
    "daman & diu": "Daman and Diu",
    "arunanchal pradesh": "Arunachal Pradesh",
}

METRICS: Final = {
    "Literacy Rate": {
        "label": "Literacy Rate (%)",
        "format": ".2f",
        "suffix": "%",
        "colorscale": "YlGnBu",
    },
    "Population Density": {
        "label": "Population Density (people per km²)",
        "format": ",.0f",
        "suffix": " people/km²",
        "colorscale": "OrRd",
    },
    "Population": {
        "label": "Total Population",
        "format": ",.0f",
        "suffix": " people",
        "colorscale": "Viridis",
    },
    "Per Capita Income": {
        "label": "Per Capita Income (INR)",
        "format": ",.0f",
        "prefix": "₹",
        "suffix": "",
        "colorscale": "Plasma",
    },
}


def _round_coordinates(value: Any, precision: int = 4) -> Any:
    """Reduce web-map payload size without changing feature topology."""

    if isinstance(value, float):
        return round(value, precision)
    if isinstance(value, list):
        for index, item in enumerate(value):
            value[index] = _round_coordinates(item, precision)
        return value
    return value


def canonicalize_state(value: object) -> str:
    """Normalize historical spellings and ampersand variants for joining."""

    text = " ".join(str(value).strip().split())
    key = text.casefold()
    return STATE_ALIASES.get(key, text)


def download_geojson(path: Path = DEFAULT_GEOJSON, refresh: bool = False) -> Path:
    """Download and cache the versioned Census 2011 state boundary file."""

    if path.exists() and path.stat().st_size > 1000 and not refresh:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        GEOJSON_URL, headers={"User-Agent": "india-state-development-study/1.0"}
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        content = response.read()
    if len(content) < 1000:
        raise ValueError("Downloaded GeoJSON is unexpectedly small")
    path.write_bytes(content)
    return path


def load_geojson(path: Path) -> dict[str, Any]:
    """Load, canonicalize, and validate the 35-feature Census 2011 geometry."""

    geojson = json.loads(path.read_text(encoding="utf-8"))
    features = geojson.get("features", [])
    if len(features) != 35:
        raise ValueError(f"Expected 35 Census 2011 state/UT features, found {len(features)}")
    for feature in features:
        properties = feature.setdefault("properties", {})
        source_name = properties.get("state_name_harmonized") or properties.get("state_name")
        if not source_name:
            raise ValueError("Every GeoJSON feature must have a state name")
        properties["state_key"] = canonicalize_state(source_name)
        properties["display_name"] = properties["state_key"]
        geometry = feature.get("geometry") or {}
        geometry["coordinates"] = _round_coordinates(geometry.get("coordinates", []))
    keys = [feature["properties"]["state_key"] for feature in features]
    if len(keys) != len(set(keys)):
        raise ValueError("Canonical GeoJSON state names are not unique")
    if "Telangana" in keys or "Ladakh" in keys:
        raise ValueError("The boundary file must preserve Census 2011 state definitions")
    return geojson


def prepare_map_data(data: pd.DataFrame, geojson: dict[str, Any]) -> pd.DataFrame:
    """Left-join project indicators onto every 2011 geographic feature."""

    required = {"State", *METRICS}
    missing = required.difference(data.columns)
    if missing:
        raise ValueError(f"Processed dataset missing map columns: {sorted(missing)}")
    values = data[["State", *METRICS]].copy()
    values["State"] = values["State"].map(canonicalize_state)
    if values["State"].duplicated().any():
        raise ValueError("Processed dataset has duplicate canonical state names")
    geography = pd.DataFrame(
        {
            "State": [f["properties"]["state_key"] for f in geojson["features"]],
            "Source Boundary Name": [f["properties"].get("state_name") for f in geojson["features"]],
        }
    )
    merged = geography.merge(values, on="State", how="left", validate="one_to_one")
    merged["Data Status"] = merged[list(METRICS)].notna().any(axis=1).map(
        {True: "Available", False: "No project observation"}
    )
    return merged


def build_figure(merged: pd.DataFrame, geojson: dict[str, Any]) -> dict[str, Any]:
    """Create a Plotly-compatible figure dictionary with metric controls."""

    locations = merged["State"].tolist()
    base_hover = [
        f"<b>{state}</b><br>{'No project observation' if status != 'Available' else 'Select a metric'}"
        for state, status in zip(merged["State"], merged["Data Status"])
    ]
    traces: list[dict[str, Any]] = [
        {
            "type": "choropleth",
            "geojson": geojson,
            "featureidkey": "properties.state_key",
            "locations": locations,
            "z": [0] * len(locations),
            "text": base_hover,
            "hovertemplate": "%{text}<extra></extra>",
            "colorscale": [[0, "#d1d5db"], [1, "#d1d5db"]],
            "showscale": False,
            "marker": {"line": {"color": "#ffffff", "width": 0.7}},
            "name": "Census 2011 boundaries",
        }
    ]
    for index, (column, settings) in enumerate(METRICS.items()):
        available = merged[merged[column].notna()]
        prefix = settings.get("prefix", "")
        suffix = settings.get("suffix", "")
        traces.append(
            {
                "type": "choropleth",
                "geojson": geojson,
                "featureidkey": "properties.state_key",
                "locations": available["State"].tolist(),
                "z": available[column].astype(float).tolist(),
                "text": available["State"].tolist(),
                "hovertemplate": (
                    f"<b>%{{text}}</b><br>{settings['label']}: "
                    f"{prefix}%{{z:{settings['format']}}}{suffix}<extra></extra>"
                ),
                "colorscale": settings["colorscale"],
                "visible": index == 0,
                "marker": {"line": {"color": "#ffffff", "width": 0.8}},
                "colorbar": {"title": {"text": settings["label"]}, "thickness": 14},
                "name": settings["label"],
            }
        )
    buttons = []
    for selected, settings in enumerate(METRICS.values(), start=1):
        visible = [True] + [i == selected for i in range(1, len(METRICS) + 1)]
        buttons.append(
            {
                "label": settings["label"],
                "method": "update",
                "args": [
                    {"visible": visible},
                    {"title.text": f"India State Development — {settings['label']} (2011/2011–12)"},
                ],
            }
        )
    return {
        "data": traces,
        "layout": {
            "title": {
                "text": "India State Development — Literacy Rate (%) (2011/2011–12)",
                "x": 0.5,
            },
            "geo": {
                "fitbounds": "locations",
                "visible": False,
                "projection": {"type": "mercator"},
                "bgcolor": "rgba(0,0,0,0)",
            },
            "updatemenus": [
                {
                    "buttons": buttons,
                    "direction": "down",
                    "showactive": True,
                    "x": 0,
                    "xanchor": "left",
                    "y": 1.04,
                    "yanchor": "bottom",
                }
            ],
            "margin": {"l": 8, "r": 8, "t": 115, "b": 8},
            "height": 700,
            "paper_bgcolor": "white",
            "font": {"family": "Arial, sans-serif", "color": "#172033"},
        },
    }


def _fallback_html(figure: dict[str, Any]) -> str:
    """Render with Plotly.js CDN when the optional Python package is absent."""

    payload = json.dumps(figure, ensure_ascii=False, separators=(",", ":"))
    return f"""<!doctype html>
<html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">
<title>India State Development Choropleth</title>
<script src=\"https://cdn.plot.ly/plotly-3.1.0.min.js\"></script>
<style>body{{font-family:Arial,sans-serif;margin:0;color:#172033}}main{{max-width:1100px;margin:auto;padding:12px}}#map{{width:100%;min-height:620px}}.note{{font-size:.82rem;line-height:1.45;color:#44506a}}@media(max-width:600px){{main{{padding:4px}}#map{{min-height:540px}}}}</style></head>
<body><main><div id=\"map\" role=\"img\" aria-label=\"Interactive choropleth map of Census 2011 Indian states and union territories\"></div>
<p class=\"note\"><strong>Sources:</strong> Census 2011 indicators and RBI/MoSPI-derived state statistics from the project pipeline. Boundaries: <a href=\"https://github.com/saketlab/censusindia/blob/master/inst/extdata/india-census-2011-states.geojson\">saketlab/censusindia Census 2011 state GeoJSON</a> (MIT-licensed repository; boundaries collated via BharatViz from Jolad &amp; Singh and ramSeraph/indian_admin_boundaries). Grey territories have no matched project observation.</p>
<p class=\"note\"><strong>Boundary note:</strong> The geometry and indicators use 2011 definitions: Andhra Pradesh is undivided; Jammu and Kashmir includes present-day Ladakh. Telangana and Ladakh are therefore not separate observations.</p></main>
<script>const fig={payload};Plotly.newPlot('map',fig.data,fig.layout,{{responsive:true,displaylogo:false}});</script></body></html>"""


def write_outputs(
    figure: dict[str, Any], html_path: Path = DEFAULT_HTML, png_path: Path | None = DEFAULT_PNG
) -> tuple[Path, Path | None]:
    """Write standalone HTML and, when Kaleido is available, a PNG preview."""

    html_path.parent.mkdir(parents=True, exist_ok=True)
    png_written: Path | None = None
    try:
        import plotly.io as pio

        html = pio.to_html(
            figure,
            full_html=True,
            include_plotlyjs=True,
            config={"responsive": True, "displaylogo": False},
        )
        source_note = (
            "<p style='font:13px Arial;color:#44506a'><b>Sources:</b> project Census 2011 and "
            "RBI/MoSPI-derived indicators; saketlab/censusindia 2011 state GeoJSON. "
            "2011 boundaries retain undivided Andhra Pradesh and Jammu & Kashmir.</p>"
        )
        html = html.replace("</body>", source_note + "</body>")
        html_path.write_text(html, encoding="utf-8")
        if png_path is not None:
            try:
                pio.write_image(figure, png_path, width=1400, height=900, scale=1.5)
                png_written = png_path
            except Exception as exc:  # Kaleido/Chrome is optional.
                LOGGER.warning("PNG export skipped: %s", exc)
    except ImportError:
        LOGGER.warning("Plotly Python not installed; writing CDN-backed HTML fallback")
        html_path.write_text(_fallback_html(figure), encoding="utf-8")
    return html_path, png_written


def generate_map(
    input_path: Path = DEFAULT_INPUT,
    geojson_path: Path = DEFAULT_GEOJSON,
    html_path: Path = DEFAULT_HTML,
    png_path: Path | None = DEFAULT_PNG,
    refresh_geojson: bool = False,
) -> tuple[Path, Path | None]:
    """Run the end-to-end map build from processed, non-synthetic data."""

    data = pd.read_csv(input_path)
    boundary_path = download_geojson(geojson_path, refresh_geojson)
    geojson = load_geojson(boundary_path)
    merged = prepare_map_data(data, geojson)
    LOGGER.info(
        "Mapped %d/%d Census 2011 states/UTs; no-data areas: %s",
        (merged["Data Status"] == "Available").sum(),
        len(merged),
        ", ".join(merged.loc[merged["Data Status"] != "Available", "State"]),
    )
    return write_outputs(build_figure(merged, geojson), html_path, png_path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--geojson", type=Path, default=DEFAULT_GEOJSON)
    parser.add_argument("--output", type=Path, default=DEFAULT_HTML)
    parser.add_argument("--png", type=Path, default=DEFAULT_PNG)
    parser.add_argument("--no-png", action="store_true")
    parser.add_argument("--refresh-geojson", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    html, png = generate_map(
        args.input,
        args.geojson,
        args.output,
        None if args.no_png else args.png,
        args.refresh_geojson,
    )
    print(f"Interactive map: {html}")
    if png:
        print(f"PNG preview: {png}")


if __name__ == "__main__":
    main()
