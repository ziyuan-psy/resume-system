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
LIBRARY_INDEX_PATH = ROOT / "library_index.md"
LOG_PATH = EXTRACTED_DIR / "extraction_log.md"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


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


def normalize_key(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip()).lower()


def group_key(row: dict[str, str]) -> tuple[str, str, str, str]:
    return (
        normalize_key(row["section_name"]),
        normalize_key(row["experience_title"]),
        normalize_key(row["organization"]),
        normalize_key(row["date"]),
    )


def source_reference(row: dict[str, str]) -> str:
    return (
        f"{row['source_project']} "
        f"({row['source_project_zip']}), {row['source_tex_file']}:{row['source_line_number']}"
    )


def main() -> int:
    if not RAW_BULLETS_PATH.exists():
        raise SystemExit(f"Missing {RAW_BULLETS_PATH}. Run scripts/extract_from_tex.py first.")

    raw_rows = read_csv(RAW_BULLETS_PATH)
    dedupe_counts: dict[str, int] = {}
    if DEDUPED_BULLETS_PATH.exists():
        for row in read_csv(DEDUPED_BULLETS_PATH):
            dedupe_counts[row["normalized_match_key"]] = int(row["duplicate_count"])

    groups: OrderedDict[tuple[str, str, str, str], list[dict[str, str]]] = OrderedDict()
    for row in raw_rows:
        groups.setdefault(group_key(row), []).append(row)

    with LIBRARY_INDEX_PATH.open("w", encoding="utf-8") as handle:
        handle.write("# Resume Library Index\n\n")
        handle.write(f"Generated: {datetime.now().isoformat(timespec='seconds')}\n\n")
        handle.write("## Summary\n\n")
        handle.write(f"- Raw bullet rows: {len(raw_rows)}\n")
        handle.write(f"- Conservative experience groups: {len(groups)}\n")
        handle.write("- Status: all generated experience YAML files default to `needs_review`.\n")
        handle.write("- Scope: active LaTeX bullets only; commented bullets are excluded from MVP outputs.\n\n")
        handle.write("## Experiences\n\n")

        for index, (_, rows) in enumerate(groups.items(), start=1):
            first = rows[0]
            title = first["experience_title"] or "Untitled Experience"
            organization = first["organization"] or ""
            date = first["date"] or ""
            section = first["section_name"] or ""
            tools = sorted(
                {
                    tool.strip()
                    for row in rows
                    for tool in row["detected_tools"].split(";")
                    if tool.strip()
                }
            )
            handle.write(f"### {index}. {title}\n\n")
            handle.write(f"- Status: needs_review\n")
            handle.write(f"- Section: {section}\n")
            handle.write(f"- Organization: {organization}\n")
            handle.write(f"- Date: {date}\n")
            handle.write(f"- Source rows: {len(rows)}\n")
            handle.write(f"- Detected tools: {', '.join(tools) if tools else ''}\n\n")
            handle.write("Bullets:\n\n")

            bullet_groups: OrderedDict[str, list[dict[str, str]]] = OrderedDict()
            for row in rows:
                bullet_groups.setdefault(row["bullet_text"], []).append(row)

            for bullet_text, bullet_rows in bullet_groups.items():
                duplicate_count = dedupe_counts.get(normalize_for_match(bullet_text), len(bullet_rows))
                handle.write(f"- {bullet_text}\n")
                handle.write(f"  - Duplicate count: {duplicate_count}\n")
                handle.write("  - Source references:\n")
                for row in bullet_rows:
                    handle.write(f"    - {source_reference(row)}\n")
            handle.write("\n")

    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write("\n## Library Index\n\n")
        handle.write(f"Generated: {datetime.now().isoformat(timespec='seconds')}\n\n")
        handle.write(f"- Library index path: `{LIBRARY_INDEX_PATH.relative_to(ROOT)}`\n")
        handle.write(f"- Experience groups included: {len(groups)}\n")

    print(f"Raw bullet rows indexed: {len(raw_rows)}")
    print(f"Conservative experience groups indexed: {len(groups)}")
    print(f"Wrote {LIBRARY_INDEX_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
