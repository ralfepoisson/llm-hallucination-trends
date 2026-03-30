#!/usr/bin/env python3
"""
Generate three date-based hallucination trend graphs from the Vectara leaderboard history CSV.

Inputs:
    - CSV with columns:
        commit_id, commit_date, model, hallucination_rate,
        factual_consistency_rate, answer_rate, average_summary_length

Outputs:
    - hallucination_central_tendency.png
    - hallucination_frontier.png
    - hallucination_variance.png

Example:
    python generate_hallucination_graphs.py readme_leaderboard_history.csv --output-dir output
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt


def load_and_prepare(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)

    required = {
        "commit_id",
        "commit_date",
        "model",
        "hallucination_rate",
    }
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    # Clean percentage-like fields such as '3.0 %' or '-' into numeric form.
    df["hallucination_rate"] = (
        df["hallucination_rate"]
        .astype(str)
        .str.replace("%", "", regex=False)
        .str.strip()
        .replace("-", pd.NA)
    )
    df["hallucination_rate"] = pd.to_numeric(df["hallucination_rate"], errors="coerce")

    # Parse commit_date at day level.
    df["commit_date"] = pd.to_datetime(df["commit_date"], errors="coerce")
    df = df.dropna(subset=["commit_date"])

    # Aggregate to date level. If there were multiple README commits on the same day,
    # they are collapsed into a single daily observation here.
    agg = (
        df.groupby("commit_date")["hallucination_rate"]
        .agg(mean="mean", median="median", std="std", best="min")
        .reset_index()
        .rename(columns={"commit_date": "date"})
        .sort_values("date")
    )

    return agg


def add_smoothed_series(agg: pd.DataFrame, window: int) -> pd.DataFrame:
    out = agg.copy()
    min_periods = 1
    out["mean_smooth"] = out["mean"].rolling(window=window, min_periods=min_periods).mean()
    out["median_smooth"] = out["median"].rolling(window=window, min_periods=min_periods).mean()
    out["best_smooth"] = out["best"].rolling(window=window, min_periods=min_periods).mean()
    out["std_smooth"] = out["std"].rolling(window=window, min_periods=min_periods).mean()
    return out


def save_central_tendency_plot(agg: pd.DataFrame, output_dir: Path) -> Path:
    path = output_dir / "hallucination_central_tendency.png"
    plt.figure(figsize=(10, 6))
    plt.plot(agg["date"], agg["mean_smooth"], label="Mean (smoothed)")
    plt.plot(agg["date"], agg["median_smooth"], label="Median (smoothed)")
    plt.xlabel("Date")
    plt.ylabel("Hallucination Rate")
    plt.title("Hallucination Trends Over Time (Date-based)")
    plt.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(path, dpi=200, bbox_inches="tight")
    plt.close()
    return path


def save_frontier_plot(agg: pd.DataFrame, output_dir: Path) -> Path:
    path = output_dir / "hallucination_frontier.png"
    plt.figure(figsize=(10, 6))
    plt.plot(agg["date"], agg["best_smooth"], linestyle="--", label="Frontier (Best Model)")
    plt.xlabel("Date")
    plt.ylabel("Hallucination Rate")
    plt.title("Frontier Trend Over Time")
    plt.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(path, dpi=200, bbox_inches="tight")
    plt.close()
    return path


def save_variance_plot(agg: pd.DataFrame, output_dir: Path) -> Path:
    path = output_dir / "hallucination_variance.png"
    plt.figure(figsize=(10, 6))
    plt.plot(agg["date"], agg["std_smooth"], label="Std Dev (Variance)")
    plt.xlabel("Date")
    plt.ylabel("Standard Deviation")
    plt.title("Variance Over Time")
    plt.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(path, dpi=200, bbox_inches="tight")
    plt.close()
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate three hallucination trend graphs from a leaderboard history CSV."
    )
    parser.add_argument(
        "csv_path",
        type=Path,
        help="Path to readme_leaderboard_history.csv",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("graphs"),
        help="Directory where PNG files will be written (default: graphs)",
    )
    parser.add_argument(
        "--window",
        type=int,
        default=7,
        help="Rolling smoothing window in days/observations (default: 7)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    agg = load_and_prepare(args.csv_path)
    agg = add_smoothed_series(agg, window=args.window)

    files = [
        save_central_tendency_plot(agg, args.output_dir),
        save_frontier_plot(agg, args.output_dir),
        save_variance_plot(agg, args.output_dir),
    ]

    print("Created:")
    for file in files:
        print(f" - {file}")


if __name__ == "__main__":
    main()
