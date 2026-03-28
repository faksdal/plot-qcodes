
# ——— File info ————————————————————————————————————————————————————————————————
# Filename      : plot-qcodes.py
# Description   : Plot qcodes as percentage of total from CSV files, with
#                 filtering options.
#
# Usage         : See --help output for details.
#
# Thanks to AI!
#
# -jole 2026
#
# ——————————————————————————————————————————————————————————————————————————————



# ——— Import section ———————————————————————————————————————————————————————————
from __future__ import annotations

import argparse
import webbrowser

import numpy    as np
import pandas   as pd               # To read csv's
                                    # For pandas, see: https://pandas.pydata.org/
import plotly.graph_objects as go   # To build the figure
                                    # For plotting, see: https://plotly.com/python/plotly-express/

from datetime   import date
from pathlib    import Path
from typing     import Iterable

# ——— END OF import section ————————————————————————————————————————————————————



# ——— Constants ————————————————————————————————————————————————————————————————
ALL_QCODES = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "B", "D", "E", "F", "G", "H", "N", "-"]
_VALID_QCODE_SET = set(ALL_QCODES)

# Stack order for positive bars from bottom to top.
# This yields top-to-bottom: 9,8,7,6,5,4,3,2,1,0,G,H, and so on for that subset.
QCODE_STACK_BOTTOM_TO_TOP = ["-", "N", "F", "E", "D", "B", "G", "H", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9"]

# Fixed qcode palette so colors remain stable across files and selections.
QCODE_COLORS = {
    "9": "#1B5E20",  # darkest green
    "8": "#2E7D32",  # dark green
    "7": "#43A047",  # green
    "6": "#81C784",  # light green
    "5": "#C8E6C9",  # palest green
    "4": "#EF9A9A",  # pale red
    "3": "#EF5350",  # medium red
    "2": "#FF5252",  # bright red
    "1": "#F06292",  # pink-red
    "0": "#E53935",  # strong red (not blue)
    "H": "#D81B60",  # magenta-red
    "G": "#B71C1C",  # deep red
    "B": "#6D4C41",
    "D": "#5D4037",
    "E": "#546E7A",
    "F": "#455A64",
    "N": "#607D8B",
    "-": "#9E9E9E",
}
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



# ——— parse_session_types() ————————————————————————————————————————————————————
def parse_session_types(raw: str) -> list[str]:
    """
    Parse a comma-separated list of session types like 'vo,r1,r4'.
    Session types are matched case-insensitively.
    """

    parsed = [item.strip().lower() for item in raw.split(",") if item.strip()]
    if not parsed:
        raise SystemExit("--stypes string produced an empty list.")

    seen: set[str] = set()
    return [stype for stype in parsed if not (stype in seen or seen.add(stype))]
# ——— END OF parse_session_types() —————————————————————————————————————————————



# ——— session_type_from_name() —————————————————————————————————————————————————
def session_type_from_name(session_name: str) -> str:
    """
    Extract the session type from the session name.
    Example: '20230629-vo3180' -> 'vo', '20230703-r11110' -> 'r1'.
    """

    suffix = session_name.split("-", 1)[1] if "-" in session_name else session_name
    return suffix[:2].lower()
# ——— END OF session_type_from_name() ——————————————————————————————————————————



# ——— parse_date_range() ———————————————————————————————————————————————————————
def parse_date_range(raw: str) -> tuple[date, date]:
    """
    Parse a comma-separated date range string like '20230101,20231231'.
    Both bounds are inclusive. Dates must be in YYYYMMDD format.
    """
    
    # Split the input string by comma, strip whitespace, and validate that we
    # have exactly two parts
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if len(parts) != 2:
        raise SystemExit(
            "--date-range expects exactly two dates separated by a comma, "
            f"e.g. '20230101,20231231'. Got: {raw!r}"
        )
        
    # Create date objects from the two parts, validating the format and values
    parsed: list[date] = []
    for part in parts:
        try:
            parsed.append(date(int(part[:4]), int(part[4:6]), int(part[6:8])))
        except (ValueError, IndexError):
            raise SystemExit(
                f"Invalid date {part!r} in --date-range. Expected YYYYMMDD format."
            )
        
    # Validate that the start date is not after the end date, and return the tuple
    start_date, end_date = parsed    
    if start_date > end_date:
        raise SystemExit(
            f"--date-range start ({start_date}) must not be after end ({end_date})."
        )
    
    return start_date, end_date
# ——— END OF parse_date_range() ————————————————————————————————————————————————



# ——— filter_by_date_range() ———————————————————————————————————————————————————
def filter_by_date_range(df: pd.DataFrame,
                         date_range: tuple[date, date] | None = None
                        ) -> pd.DataFrame:
    """
    Filter rows whose session name starts with a YYYYMMDD date within [start, end].
    Example: '20230629-vo3180' -> date(2023, 6, 29).
    """

    # Don't filter if no date range is provided; just return the original DataFrame
    if date_range is None:
        return df

    # Unpack the date range tuple into start_date and end_date for easier access
    start_date, end_date    = date_range
    
    # Identify the session column (e.g. "VgosDB" or the first column) to
    # extract session names
    session_col             = find_session_column(df)

    # ——— _date_from_name() ————————————————————————————————————————————————————
    def _date_from_name(name: str) -> date | None:
        """
        Extract a date object from the session name if it starts with a valid
        YYYYMMDD prefix. If the prefix is missing or invalid, return None.
        """
        try:
            prefix = name[:8]
            return date(int(prefix[:4]), int(prefix[4:6]), int(prefix[6:8]))
        except (ValueError, IndexError):
            return None
    # ——— END OF _date_from_name() —————————————————————————————————————————————

    # Map session names to dates, filter by the specified date range, and return
    # a new DataFrame containing only the rows that match the date criteria.
    dates = df[session_col].astype(str).map(_date_from_name)

    # Create a boolean mask where True indicates rows with valid dates within
    # the specified range
    # Rows with invalid or out-of-range dates will be False.
    mask = dates.map(lambda d: d is not None and start_date <= d <= end_date)
    
    # Use the mask to filter the DataFrame and return a copy of the filtered data.
    return df.loc[mask].copy()
# ——— END OF filter_by_date_range() ————————————————————————————————————————————



# ——— filter_by_session_types() ————————————————————————————————————————————————
def filter_by_session_types(df: pd.DataFrame, stypes: list[str] | None = None) -> pd.DataFrame:
    """
    Filter rows by session type using the first two characters after the date prefix.
    """

    # If no session types are provided, return the original DataFrame without
    # filtering.
    if stypes is None:
        return df

    # Identify the session column (e.g. "VgosDB" or the first column) to extract
    # session names
    session_col = find_session_column(df)

    # Map session names to their types using session_type_from_name, create a
    # boolean mask where True indicates rows with a session type in the
    # specified list.
    session_names = df[session_col].astype(str)

    # The session type is determined by the first two characters after the date
    # prefix (if present)
    mask = session_names.map(lambda name: session_type_from_name(name) in set(stypes))
    
    # Use the mask to filter the DataFrame and return a copy of the filtered data
    return df.loc[mask].copy()
# ——— END OF filter_by_session_types() —————————————————————————————————————————



# ——— find_session_column() ————————————————————————————————————————————————————
def find_session_column(df: pd.DataFrame) -> str:
    if "VgosDB" in df.columns:
        return "VgosDB"
    return df.columns[0]
# ——— END OF find_session_column() —————————————————————————————————————————————



# ——— active_qcodes_for_selection() ——————————————————————————————————————————
def active_qcodes_for_selection(qcodes: list[str] | None = None) -> list[str]:
    """Return qcodes in plotting stack order for the current selection."""

    selected_qcodes = qcodes if qcodes is not None else ALL_QCODES
    return [q for q in QCODE_STACK_BOTTOM_TO_TOP if q in selected_qcodes]
# ——— END OF active_qcodes_for_selection() ———————————————————————————————————



# ——— build_percentage_figure() ————————————————————————————————————————————————
def build_percentage_figure(    df      : pd.DataFrame,
                                title   : str,
                                qcodes  : list[str] | None = None
                            ) -> go.Figure:
    """
    Build a Plotly figure showing the percentage of each qcode relative to
    the total.
    The qcodes parameter allows selecting a subset of codes to include in
    the plot.
    """

    # Identify the session column (e.g. "VgosDB" or the first column)
    session_col     = find_session_column(df)

    # Determine which qcodes to include based on the provided list or default
    # to all, then reorder for plotting so stack layers are deterministic.
    active_qcodes   = active_qcodes_for_selection(qcodes)
    qcode_cols      = [f"Total_{q}" for q in active_qcodes]

    # Ensure every requested qcode is present; missing columns count as 0.
    for col in qcode_cols:
        if col not in df.columns:
            df[col] = 0

    counts      = df[qcode_cols].apply(pd.to_numeric, errors="coerce").fillna(0)
    total       = counts.sum(axis=1)
    safe_total  = total.replace(0, np.nan)
    pct         = counts.div(safe_total, axis=0).fillna(0) * 100

    # Build display labels once (session suffix + formatted date), row by row.
    session_name = (
        df[session_col]
        .astype(str)
        .str.split("-", n=1)
        .str[1]
        .fillna("")
        .str.upper()
    )
    session_raw = df[session_col].astype(str)
    date_ddmmyyyy = (
        pd.to_datetime(
            session_raw.str.slice(0, 8),
            format="%Y%m%d",
            errors="coerce",
        )
        .dt.strftime("%d/%m/%Y")
        .fillna("")
    )
    x_label = session_name + " - " + date_ddmmyyyy
    
    # Create the plotly graph object
    fig = go.Figure()

    # Add a bar trace for each active qcode, using the percentage values for
    # the y-axis
    for q in active_qcodes:
        col         = f"Total_{q}"
        customdata  = np.column_stack((counts[col].to_numpy(), total.to_numpy()))
        
        fig.add_bar(
            x               = x_label,
            y               = pct[col],
            name            = f"Q-code {q}",
            marker_color    = QCODE_COLORS.get(q, "#888888"),
            customdata      = customdata,
            hovertemplate   = (f"Q-code {q}: %{{y:.2f}}%<extra></extra>")            
        )

    fig.update_layout(
        title       = title,
        barmode     = "relative",
        hovermode   = "x unified",
        xaxis       = dict(title="Session", tickangle=45),
        yaxis       = dict(title="Qcode share of total (%)", range=[0, 100]),
        
        # Settings for the plot legend
        legend = dict(title=dict(text="Q-codes"), traceorder="reversed",),
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
                qcodes      : list[str] | None = None,
                stypes      : list[str] | None = None,
                date_range  : tuple[date, date] | None = None,
                skip_empty  : bool = False
            ) -> None:
    """
    Read the CSV file, build the percentage figure, and save as HTML.
    The title and qcodes parameters are passed to the figure builder.
    """

    # Read the CSV file into a DataFrame. We use skipinitialspace=True to handle
    # any spaces after commas in the header or data
    df = pd.read_csv(input_path, skipinitialspace=True)

    # If session type filtering is requested, apply it to the DataFrame
    # This will reduce the DataFrame to only the rows that match the specified
    # session types
    df = filter_by_session_types(df, stypes=stypes)

    # If date range filtering is requested, apply it to the DataFrame
    # This will reduce the DataFrame to only the rows that have session names
    # starting with a date within the specified range
    df = filter_by_date_range(df, date_range=date_range)

    # If requested, omit sessions where all relevant qcode counts are zero.
    if skip_empty:
        qcode_cols = [f"Total_{q}" for q in active_qcodes_for_selection(qcodes)]
        for col in qcode_cols:
            if col not in df.columns:
                df[col] = 0
        non_empty_mask = (
            df[qcode_cols].apply(pd.to_numeric, errors="coerce").fillna(0).sum(axis=1) > 0
        )
        df = df.loc[non_empty_mask].copy()

    if df.empty:
        raise SystemExit(
            f"No sessions matched the given filters in file: {input_path}"
        )

    # Set the title for the plot. If a custom title is provided, use it;
    # otherwise, generate a default title based on the input filename.
    use_title = title or f"Qcodes as percent of total - {input_path.stem}"
    
    # Build the figure using the DataFrame, title, and selected qcodes.
    fig = build_percentage_figure(df, use_title, qcodes=qcodes)
    
    # Save the figure as an HTML file at the specified output path, and tell
    # the user where it was saved
    fig.write_html(output_path)
    print(f"Wrote: {output_path}")
# ——— END OF plot_csv() ————————————————————————————————————————————————————————



# ——— open_in_browser() ————————————————————————————————————————————————————————
def open_in_browser(path: Path) -> None:
    """
    Attempt to open the given file path in the default web browser.
    We convert the path to an absolute URI and use webbrowser.open, which should
    work across platforms. We also catch exceptions and print a message if it fails.
    """

    try:
        opened = webbrowser.open(path.resolve().as_uri())
        if not opened:
            print(f"Could not open automatically: {path}")
    except Exception as exc:
        print(f"Could not open {path}: {exc}")
# ——— END OF open_in_browser() —————————————————————————————————————————————————



# ——— main() ———————————————————————————————————————————————————————————————————
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
            "Comma-separated session types to include, e.g. 'vo,r1,r4'. "
            "Session type is taken from the first two characters after the '-'."
        ),
    )
    parser.add_argument(
        "--date-range",
        metavar="RANGE",
        default=None,
        help=(
            "Comma-separated date range to include, e.g. '20230101,20231231'. "
            "Dates should be in YYYYMMDD format, as in the csv files."

        ),
    )
    parser.add_argument(
        "--open",
        action="store_true",
        help="Open generated HTML file(s) in the default browser",
    )
    parser.add_argument(
        "--skip-empty",
        action="store_true",
        help="Omit sessions where all relevant qcode counts are zero",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    # Expand input paths, handle defaults and deduplication.
    inputs = expand_inputs(args.inputs)
    if not inputs:
        raise SystemExit("No input CSV files found.")

    # Parse qcodes if provided, validate against allowed set.
    selected_qcodes = parse_qcodes(args.qcodes) if args.qcodes else None

    # Parse session types if provided, plotting only session types given by
    # the user
    # If not provided, all session types are included
    selected_stypes = parse_session_types(args.stypes) if args.stypes else None
    selected_date_range = parse_date_range(args.date_range) if args.date_range else None

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
        plot_csv(
            input_path,
            output_path,
            title=args.title,
            qcodes=selected_qcodes,
            stypes=selected_stypes,
            date_range=selected_date_range,
            skip_empty=args.skip_empty,
        )
        
        # Open the generated HTML file if requested
        if args.open:
            open_in_browser(output_path)

    return 0
# ——— END OF main() ————————————————————————————————————————————————————————————


if __name__ == "__main__":
    raise SystemExit(main())

