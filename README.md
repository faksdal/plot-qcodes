# Plot Qcodes

Generate interactive stacked bar plots of Qcode composition from CSV files, where each Qcode is shown as percentage of the total per session.

The script supports these Qcodes:

0, 1, 2, 3, 4, 5, 6, 7, 8, 9, B, D, E, F, G, H, N, -

It is robust to CSV files that contain only a subset of these columns: missing Qcode columns are treated as zero.

## Inputs Expected

- CSV files with one row per session.
- A session identifier column (preferred name: VgosDB).
- Qcode count columns named like Total_0, Total_1, ..., Total_H, Total_N, Total_-.

## Setup

1. Create and activate a virtual environment (optional but recommended).
2. Install dependencies:

	pip install -r requirements.txt

## Usage

Run on a single CSV file:

python plot_qcodes.py qcodes_Nn_2010_2026.csv

Run on all CSV files in the current directory:

python plot_qcodes.py

Open generated plot(s) automatically in your default browser:

python plot_qcodes.py qcodes_Nn_2010_2026.csv --open

Batch mode with browser open:

python plot_qcodes.py --open

Custom output file name (single input only):

python plot_qcodes.py qcodes_Nn_2010_2026.csv --output my_plot.html

Custom chart title:

python plot_qcodes.py qcodes_Nn_2010_2026.csv --title "NYALES20 Qcodes"

You can also pass glob patterns, for example:

python plot_qcodes.py "*Sband*.CSV"

## Output

By default, each input CSV generates one HTML file named:

<input_stem>_qcodes.html

Each plot is an interactive Plotly chart with:

- Stacked bars in percent (0 to 100)
- Unified hover by session
- Hover details with raw count, total scans, and percent

## Notes

- Rows where all Qcode counts are zero are kept; percentages are shown as 0.
- If VgosDB is not present, the first CSV column is used for the x-axis labels.
