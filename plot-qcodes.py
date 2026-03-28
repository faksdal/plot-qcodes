
# ——— Import section ———————————————————————————————————————————————————————————
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable
import webbrowser

import numpy as np
import pandas as pd                 # To read csv's
                                    # For pandas, see: https://pandas.pydata.org/
import plotly.graph_objects as go   # To build the figure
                                    # For plotting, see: https://plotly.com/python/plotly-express/
# ——— END OF import section ————————————————————————————————————————————————————



# ——— Constants ————————————————————————————————————————————————————————————————
ALL_QCODES = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "B", "D", "E", "F", "G", "H", "N", "-"]
_VALID_QCODE_SET = set(ALL_QCODES)
# ——— END OF Constants —————————————————————————————————————————————————————————



# ——— parse_qcodes() ———————————————————————————————————————————————————————————
def parse_qcodes(raw: str) -> list[str]:
    """
    Parse a compact qcode string like '0123BD-' into an ordered list.
    """

    # Validate characters and preserve order without duplicates.
    seen    : set[str]  = set()
    result  : list[str] = []

    # Parse the input string, validate against allowed qcodes, and build a list
    # of unique codes.
    # The qcodes are case-insensitive, but we will store them in uppercase form.
    for ch in raw.upper():
        if ch not in _VALID_QCODE_SET:
            raise SystemExit(
                f"Unknown qcode '{ch}'. Valid codes: {''.join(ALL_QCODES)}"
            )
        if ch not in seen:
            seen.add(ch)
            result.append(ch)
    
    # If the result is empty, it means the input string had no valid qcodes.
    if not result:
        raise SystemExit("--qcodes string produced an empty list.")
    
    # Preserve the canonical order from ALL_QCODES.
    return [q for q in ALL_QCODES if q in seen]
# ——— END OF parse_qcodes() ————————————————————————————————————————————————————



# ——— find_session_column() ————————————————————————————————————————————————————
def find_session_column(df: pd.DataFrame) -> str:
    if "VgosDB" in df.columns:
        return "VgosDB"
    return df.columns[0]
# ——— END OF find_session_column() —————————————————————————————————————————————



# ——— build_percentage_figure() ————————————————————————————————————————————————
def build_percentage_figure(    df      : pd.DataFrame,
                                title   : str,
                                qcodes  : list[str] | None = None
                            ) -> go.Figure:
    """
    Build a Plotly figure showing the percentage of each qcode relative to the total.
    The qcodes parameter allows selecting a subset of codes to include in the plot.
    """

    # Identify the session column (e.g. "VgosDB" or the first column)
    session_col     = find_session_column(df)

    # Determine which qcodes to include based on the provided list or default
    # to all
    active_qcodes   = qcodes if qcodes is not None else ALL_QCODES
    qcode_cols      = [f"Total_{q}" for q in active_qcodes]

    # Ensure every requested qcode is present; missing columns count as 0.
    for col in qcode_cols:
        if col not in df.columns:
            df[col] = 0

    counts = df[qcode_cols].apply(pd.to_numeric, errors="coerce").fillna(0)
    total = counts.sum(axis=1)
    safe_total = total.replace(0, np.nan)
    pct = counts.div(safe_total, axis=0).fillna(0) * 100

    fig = go.Figure()
    for q in active_qcodes:
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
# ——— END OF build_percentage_figure() —————————————————————————————————————————



# ——— output_name_for() ————————————————————————————————————————————————————————
def output_name_for(input_path: Path) -> Path:
    """
    Generate an output HTML filename based on the input CSV filename.
    E.g. "qcodes_Ny_2010_2026.csv" -> "qcodes_Ny_2010_2026_qcodes.html"
    """

    return input_path.with_name(f"{input_path.stem}_qcodes.html")
# ——— END OF output_name_for() —————————————————————————————————————————————————



# ——— expand_inputs() ——————————————————————————————————————————————————————————
def expand_inputs(raw_inputs: list[str]) -> list[Path]:
    
    """ 
    Expand raw input strings into a list of Path objects. Handles global patterns
    and deduplication.
    If raw_inputs is empty, defaults to all *.csv and *.CSV files in the current directory.
    """

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

# ——— END OF expand_inputs() ———————————————————————————————————————————————————



# ——— plot_csv() ———————————————————————————————————————————————————————————————
def plot_csv(   input_path  : Path,
                output_path : Path,
                title       : str | None = None,
                qcodes      : list[str] | None = None
            ) -> None:
    """
    Read the CSV file, build the percentage figure, and save as HTML.
    The title and qcodes parameters are passed to the figure builder.
    """

    # Read the CSV file into a DataFrame. We use skipinitialspace=True to handle
    # any spaces after commas in the header or data.
    df = pd.read_csv(input_path, skipinitialspace=True)

    # Set the title for the plot. If a custom title is provided, use it;
    # otherwise, generate a default title based on the input filename.
    use_title = title or f"Qcodes as percent of total - {input_path.stem}"
    
    # Build the figure using the DataFrame, title, and selected qcodes.
    fig = build_percentage_figure(df, use_title, qcodes=qcodes)
    
    fig.write_html(output_path)
    print(f"Wrote: {output_path}")
# ——— END OF plot_csv() ————————————————————————————————————————————————————————



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
        help=(
            "Output HTML path (only valid when one input file resolves). "
            "Defaults to input filename with '_qcodes.html' suffix."
        ),
    )
    parser.add_argument("--title", help="Custom plot title")
    parser.add_argument(
        "--qcodes",
        metavar="CODES",
        default=None,
        help=(
            "Compact string of qcodes to include, e.g. '0123BD-'. "
            f"Valid codes: {''.join(ALL_QCODES)}. Defaults to all."
        ),
    )
    parser.add_argument(
        "--stypes",
        metavar="TYPES",
        default=None,
        help=(
            "Comma separated string of session types to include, e.g. 'vo, r1, r4'. "
            # f"Valid codes: {''.join(ALL_QCODES)}. Defaults to all."
        ),
    )
    parser.add_argument(
        "--open",
        action="store_true",
        help="Open generated HTML file(s) in the default browser",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    # Expand input paths, handle defaults and deduplication.
    inputs = expand_inputs(args.inputs)
    if not inputs:
        raise SystemExit("No input CSV files found.")

    # Parse qcodes if provided, validate against allowed set.
    selected_qcodes = parse_qcodes(args.qcodes) if args.qcodes else None

    # Validate --output usage: only allowed if exactly one input file is provided.
    if args.output is not None and len(inputs) != 1:
        raise SystemExit("--output can only be used when exactly one input file is provided.")

    # Process each input file, generate corresponding output, and optionally
    # open in browser.
    for input_path in inputs:
        if not input_path.exists() or not input_path.is_file():
            print(f"Skipping missing file: {input_path}")
            continue

        # If --output is specified, use it for the single input file.
        # Otherwise, generate output name based on input filename.
        output_path = args.output if args.output is not None else output_name_for(input_path)
        
        # Generate the plot and save as HTML.
        plot_csv(input_path, output_path, title = args.title, qcodes = selected_qcodes)
        
        # Open the generated HTML file if requested
        if args.open:
            open_in_browser(output_path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

