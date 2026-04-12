from __future__ import annotations

import argparse
import webbrowser
from pathlib import Path

import dash
import pandas as pd
import plotly.express as px
from dash import Input, Output, dash_table, dcc, html


def _latest_csv_from_outputs(project_root: Path) -> Path:
    csv_files = sorted((project_root / "outputs").rglob("*.csv"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not csv_files:
        raise FileNotFoundError("No CSV files were found under outputs/.")
    return csv_files[0]


def load_dataframe(project_root: Path, csv_path: str | None) -> tuple[pd.DataFrame, Path]:
    path = Path(csv_path).resolve() if csv_path else _latest_csv_from_outputs(project_root)
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {path}")
    dataframe = pd.read_csv(path)
    return dataframe, path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Launch the 5G NR PHY STL Dash analytics app.")
    parser.add_argument("--csv", type=str, default=None, help="CSV file to visualize. Defaults to the latest CSV in outputs/.")
    parser.add_argument("--host", type=str, default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8050)
    parser.add_argument("--title", type=str, default="5G NR PHY STL Batch Dashboard")
    parser.add_argument("--open-browser", action="store_true")
    return parser


def create_dash_app(dataframe: pd.DataFrame, csv_path: Path, title: str) -> dash.Dash:
    app = dash.Dash(__name__)
    numeric_columns = dataframe.select_dtypes(include=["number"]).columns.tolist()
    default_x = numeric_columns[0] if numeric_columns else dataframe.columns[0]
    default_y = numeric_columns[1] if len(numeric_columns) > 1 else numeric_columns[0]

    app.layout = html.Div(
        style={"fontFamily": "Arial, sans-serif", "padding": "18px", "backgroundColor": "#f8fafc"},
        children=[
            html.H2(title, style={"marginBottom": "4px"}),
            html.Div(
                [
                    html.Div(f"Source CSV: {csv_path}", style={"marginBottom": "8px"}),
                    html.Div(f"Rows: {len(dataframe)} | Columns: {len(dataframe.columns)}"),
                ],
                style={"color": "#334155", "marginBottom": "16px"},
            ),
            html.Div(
                style={"display": "grid", "gridTemplateColumns": "220px 220px 220px", "gap": "16px", "marginBottom": "16px"},
                children=[
                    html.Div([html.Label("X axis"), dcc.Dropdown(numeric_columns or dataframe.columns.tolist(), default_x, id="x-axis")]),
                    html.Div([html.Label("Y axis"), dcc.Dropdown(numeric_columns or dataframe.columns.tolist(), default_y, id="y-axis")]),
                    html.Div(
                        [
                            html.Label("Plot type"),
                            dcc.Dropdown(
                                ["line", "scatter", "bar"],
                                "line",
                                id="plot-type",
                                clearable=False,
                            ),
                        ]
                    ),
                ],
            ),
            dcc.Graph(id="metric-graph"),
            html.H4("Preview"),
            dash_table.DataTable(
                data=dataframe.head(50).to_dict("records"),
                columns=[{"name": column, "id": column} for column in dataframe.columns],
                page_size=12,
                style_table={"overflowX": "auto"},
                style_cell={"textAlign": "left", "padding": "6px"},
                style_header={"fontWeight": "bold"},
            ),
        ],
    )

    @app.callback(
        Output("metric-graph", "figure"),
        Input("x-axis", "value"),
        Input("y-axis", "value"),
        Input("plot-type", "value"),
    )
    def _update_graph(x_axis: str, y_axis: str, plot_type: str):  # pragma: no cover - Dash callback
        if plot_type == "scatter":
            figure = px.scatter(dataframe, x=x_axis, y=y_axis, title=f"{y_axis} vs {x_axis}")
        elif plot_type == "bar":
            figure = px.bar(dataframe, x=x_axis, y=y_axis, title=f"{y_axis} vs {x_axis}")
        else:
            figure = px.line(dataframe, x=x_axis, y=y_axis, markers=True, title=f"{y_axis} vs {x_axis}")
        figure.update_layout(template="plotly_white")
        return figure

    return app


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()
    project_root = Path(__file__).resolve().parent.parent
    dataframe, csv_path = load_dataframe(project_root, args.csv)
    app = create_dash_app(dataframe=dataframe, csv_path=csv_path, title=args.title)
    if args.open_browser:
        webbrowser.open(f"http://{args.host}:{args.port}", new=2)
    app.run(host=args.host, port=args.port, debug=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
