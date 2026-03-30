#!/usr/bin/env python3

import csv
import re
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = REPO_ROOT / "data" / "readme_leaderboard_history.csv"
README_PATH = "README.md"
CSV_HEADERS = [
    "commit_id",
    "commit_date",
    "model",
    "hallucination_rate",
    "factual_consistency_rate",
    "answer_rate",
    "average_summary_length",
]


def run_git_command(args):
    completed = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout


def split_markdown_row(line):
    stripped = line.strip()
    if not stripped.startswith("|"):
        return []
    return [cell.strip() for cell in stripped.strip("|").split("|")]


def normalize_header(header):
    normalized = header.lower()
    normalized = normalized.replace("(words)", "")
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return " ".join(normalized.split())


def is_separator_row(cells):
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)


def canonicalize_value(value):
    return re.sub(r"\s+", " ", value.strip())


def parse_leaderboard_rows(readme_text):
    lines = readme_text.splitlines()
    for index in range(len(lines) - 1):
        header_cells = split_markdown_row(lines[index])
        separator_cells = split_markdown_row(lines[index + 1])
        if not header_cells or not separator_cells or not is_separator_row(separator_cells):
            continue

        normalized_headers = [normalize_header(header) for header in header_cells]
        header_map = {}
        for position, header in enumerate(normalized_headers):
            if header == "model":
                header_map["model"] = position
            elif header == "hallucination rate":
                header_map["hallucination_rate"] = position
            elif header in {"factual consistency rate", "accuracy"}:
                header_map["factual_consistency_rate"] = position
            elif header == "answer rate":
                header_map["answer_rate"] = position
            elif header == "average summary length":
                header_map["average_summary_length"] = position

        if set(header_map) != {
            "model",
            "hallucination_rate",
            "factual_consistency_rate",
            "answer_rate",
            "average_summary_length",
        }:
            continue

        rows = []
        next_index = index + 2
        while next_index < len(lines):
            row_cells = split_markdown_row(lines[next_index])
            if not row_cells:
                break
            if is_separator_row(row_cells):
                next_index += 1
                continue

            if len(row_cells) < len(header_cells):
                row_cells.extend([""] * (len(header_cells) - len(row_cells)))

            row = {
                "model": canonicalize_value(row_cells[header_map["model"]]),
                "hallucination_rate": canonicalize_value(
                    row_cells[header_map["hallucination_rate"]]
                ),
                "factual_consistency_rate": canonicalize_value(
                    row_cells[header_map["factual_consistency_rate"]]
                ),
                "answer_rate": canonicalize_value(row_cells[header_map["answer_rate"]]),
                "average_summary_length": canonicalize_value(
                    row_cells[header_map["average_summary_length"]]
                ),
            }
            if row["model"]:
                rows.append(row)
            next_index += 1

        return rows

    return []


def get_readme_commits():
    output = run_git_command(
        [
            "log",
            "--follow",
            "--reverse",
            "--date=short",
            "--format=%H%x1f%ad",
            "--",
            README_PATH,
        ]
    )
    commits = []
    for line in output.splitlines():
        if not line.strip():
            continue
        commit_id, commit_date = line.split("\x1f", 1)
        commits.append({"commit_id": commit_id, "commit_date": commit_date})
    return commits


def get_readme_at_commit(commit_id):
    try:
        return run_git_command(["show", f"{commit_id}:{README_PATH}"])
    except subprocess.CalledProcessError:
        return ""


def collect_commit_history():
    history = []
    for commit in get_readme_commits():
        rows = parse_leaderboard_rows(get_readme_at_commit(commit["commit_id"]))
        if not rows:
            continue
        history.append(
            {
                "commit_id": commit["commit_id"],
                "commit_date": commit["commit_date"],
                "rows": rows,
            }
        )
    return history


def build_history_rows(commit_history):
    flattened_rows = []
    previous_models = set()

    for commit in commit_history:
        current_models = set()
        for row in commit["rows"]:
            history_row = {
                "commit_id": commit["commit_id"],
                "commit_date": commit["commit_date"],
                **row,
            }
            flattened_rows.append(history_row)
            current_models.add(row["model"])

        for deleted_model in sorted(previous_models - current_models):
            flattened_rows.append(
                {
                    "commit_id": commit["commit_id"],
                    "commit_date": commit["commit_date"],
                    "model": deleted_model,
                    "hallucination_rate": "-",
                    "factual_consistency_rate": "-",
                    "answer_rate": "-",
                    "average_summary_length": "-",
                }
            )

        previous_models = current_models

    return flattened_rows


def write_csv(rows, output_path=OUTPUT_PATH):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_HEADERS)
        writer.writeheader()
        writer.writerows(rows)


def main():
    commit_history = collect_commit_history()
    history_rows = build_history_rows(commit_history)
    write_csv(history_rows)
    print(
        f"Wrote {len(history_rows)} rows across {len(commit_history)} README commits to "
        f"{OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()
