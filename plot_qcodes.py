from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable
import webbrowser

import numpy as np
import pandas as pd
import plotly.graph_objects as go


QCODES = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "B", "D", "E", "F", "G", "H", "N", "-"]


def find_session_column(df: pd.DataFrame) -> str:
    if "VgosDB" in df.columns:
        return "VgosDB"
    return df.columns[0]


def build_percentage_figure(df: pd.DataFrame, title: str) -> go.Figure:
    session_col = find_session_column(df)
    qcode_cols = [f"Total_{q}" for q in QCODES]

    # Ensure every requested qcode is present; missing columns count as 0.
    for col in qcode_cols:
        if col not in df.columns:
            df[col] = 0

    counts = df[qcode_cols].apply(pd.to_numeric, errors="coerce").fillna(0)
    total = counts.sum(axis=1)
    safe_total = total.replace(0, np.nan)
    pct = counts.div(safe_total, axis=0).fillna(0) * 100

    fig = go.Figure()
    for q in QCODES:
        col = f"Total_{q}"
        customdata = np.column_stack((counts[col].to_numpy(), total.to_numpy()))
        fig.add_bar(
            x=df[session_col],
            y=pct[col],
            name=q,
            customdata=customdata,
            hovertemplate=(
                "<b>Session:</b> %{x}<br>"
                f"<b>Qcode:</b> {q}<br>"
                "<b>Count:</b> %{customdata[0]:.0f}<br>"
                "<b>Total:</b> %{customdata[1]:.0f}<br>"
                "<b>Percent:</b> %{y:.2f}%<extra></extra>"
            ),
        )

    fig.update_layout(
        title=title,
        barmode="relative",
        hovermode="x unified",
        xaxis=dict(title="Session", tickangle=45),
        yaxis=dict(title="Qcode share of total (%)", range=[0, 100]),
        legend=dict(traceorder="normal"),
    )
    return fig


def output_name_for(input_path: Path) -> Path:
    return input_path.with_name(f"{input_path.stem}_qcodes.html")


def expand_inputs(raw_inputs: list[str]) -> list[Path]:
    if not raw_inputs:
        paths = sorted(Path.cwd().glob("*.csv")) + sorted(Path.cwd().glob("*.CSV"))
        return paths

    out: list[Path] = []
    for item in raw_inputs:
        if any(ch in item for ch in "*?[]"):
            out.extend(sorted(Path.cwd().glob(item)))
        else:
            out.append(Path(item))

    # Keep first occurrence order, remove duplicates.
    deduped: list[Path] = []
    seen: set[Path] = set()
    for p in out:
        rp = p.resolve()
        if rp not in seen:
            seen.add(rp)
            deduped.append(p)
    return deduped


def plot_csv(input_path: Path, output_path: Path, title: str | None = None) -> None:
    df = pd.read_csv(input_path, skipinitialspace=True)
    use_title = title or f"Qcodes as percent of total - {input_path.stem}"
    fig = build_percentage_figure(df, use_title)
    fig.write_html(output_path)
    print(f"Wrote: {output_path}")


def open_in_browser(path: Path) -> None:
    try:
        opened = webbrowser.open(path.resolve().as_uri())
        if not opened:
            print(f"Could not open automatically: {path}")
    except Exception as exc:
        print(f"Could not open {path}: {exc}")


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Plot qcodes (0-9, B, D, E, F, G, H, N, -) as percentage of total scans "
            "from one or more CSV files."
        )
    )
    parser.add_argument(
        "inputs",
        nargs="*",
        help="CSV files and/or glob patterns (default: all *.csv and *.CSV in current folder)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output HTML path (only valid when one input file resolves)",
    )
    parser.add_argument("--title", help="Custom plot title")
    parser.add_argument(
        "--open",
        action="store_true",
        help="Open generated HTML file(s) in the default browser",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    inputs = expand_inputs(args.inputs)
    if not inputs:
        raise SystemExit("No input CSV files found.")

    if args.output is not None and len(inputs) != 1:
        raise SystemExit("--output can only be used when exactly one input file is provided.")

    for input_path in inputs:
        if not input_path.exists() or not input_path.is_file():
            print(f"Skipping missing file: {input_path}")
            continue

        output_path = args.output if args.output is not None else output_name_for(input_path)
        plot_csv(input_path, output_path, title=args.title)
        if args.open:
            open_in_browser(output_path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

