from __future__ import annotations

import csv
import re
from collections import OrderedDict
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTRACTED_DIR = ROOT / "extracted"
RAW_BULLETS_PATH = EXTRACTED_DIR / "raw_bullets.csv"
DEDUPED_BULLETS_PATH = EXTRACTED_DIR / "deduplicated_bullets.csv"
DUPLICATE_REPORT_PATH = EXTRACTED_DIR / "duplicate_report.md"
LOG_PATH = EXTRACTED_DIR / "extraction_log.md"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def normalize_for_match(value: str) -> str:
    value = value.lower()
    value = value.replace("\u2018", "'").replace("\u2019", "'")
    value = value.replace("\u201c", '"').replace("\u201d", '"')
    value = value.replace("\u2013", "-").replace("\u2014", "-")
    value = re.sub(r"\\[A-Za-z@]+", " ", value)
    value = re.sub(r"[{}]", " ", value)
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"\s+([,.;:!?%)])", r"\1", value)
    value = re.sub(r"([(])\s+", r"\1", value)
    return value.strip()


def source_reference(row: dict[str, str]) -> str:
    return (
        f"{row['original_zip_name']} | {row['source_project']} "
        f"({row['source_project_zip']}) | {row['source_tex_file']}:{row['source_line_number']}"
    )


def main() -> int:
    if not RAW_BULLETS_PATH.exists():
        raise SystemExit(f"Missing {RAW_BULLETS_PATH}. Run scripts/extract_from_tex.py first.")

    raw_rows = read_csv(RAW_BULLETS_PATH)
    groups: OrderedDict[str, list[dict[str, str]]] = OrderedDict()
    for row in raw_rows:
        key = normalize_for_match(row["bullet_text"])
        if key:
            groups.setdefault(key, []).append(row)

    deduped_rows: list[dict[str, object]] = []
    duplicate_groups = [(key, rows) for key, rows in groups.items() if len(rows) > 1]

    for index, (key, rows) in enumerate(groups.items(), start=1):
        canonical = rows[0].copy()
        canonical["deduplicated_bullet_id"] = f"dedup_b{index:06d}"
        canonical["duplicate_count"] = len(rows)
        canonical["normalized_match_key"] = key
        canonical["all_source_references"] = " || ".join(source_reference(row) for row in rows)
        deduped_rows.append(canonical)

    fieldnames = [
        "deduplicated_bullet_id",
        "duplicate_count",
        "normalized_match_key",
        "all_source_references",
        "bullet_id",
        "original_zip_name",
        "source_project_zip",
        "source_project",
        "source_project_id",
        "source_tex_file",
        "source_line_number",
        "section_name",
        "experience_id",
        "experience_title",
        "organization",
        "date",
        "bullet_text",
        "raw_bullet_tex",
        "detected_tools",
        "possible_role_tags",
    ]
    write_csv(DEDUPED_BULLETS_PATH, deduped_rows, fieldnames)

    with DUPLICATE_REPORT_PATH.open("w", encoding="utf-8") as handle:
        handle.write("# Duplicate Report\n\n")
        handle.write(f"Generated: {datetime.now().isoformat(timespec='seconds')}\n\n")
        handle.write(f"- Raw bullet rows: {len(raw_rows)}\n")
        handle.write(f"- Unique normalized bullets: {len(groups)}\n")
        handle.write(f"- Duplicate groups: {len(duplicate_groups)}\n\n")
        if not duplicate_groups:
            handle.write("No exact normalized duplicate bullet groups found.\n")
        for group_index, (_, rows) in enumerate(duplicate_groups, start=1):
            handle.write(f"## Duplicate Group {group_index}\n\n")
            handle.write(f"Canonical bullet text: {rows[0]['bullet_text']}\n\n")
            handle.write(f"Duplicate count: {len(rows)}\n\n")
            handle.write("Source references:\n\n")
            for row in rows:
                handle.write(f"- {source_reference(row)}\n")
            handle.write("\n")

    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write("\n## Deduplication\n\n")
        handle.write(f"Generated: {datetime.now().isoformat(timespec='seconds')}\n\n")
        handle.write(f"- Raw bullet rows: {len(raw_rows)}\n")
        handle.write(f"- Unique normalized bullet rows: {len(groups)}\n")
        handle.write(f"- Duplicate groups: {len(duplicate_groups)}\n")

    print(f"Raw bullet rows: {len(raw_rows)}")
    print(f"Unique normalized bullet rows: {len(groups)}")
    print(f"Duplicate groups: {len(duplicate_groups)}")
    print(f"Wrote {DEDUPED_BULLETS_PATH}")
    print(f"Wrote {DUPLICATE_REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
