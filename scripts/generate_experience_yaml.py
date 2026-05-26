from __future__ import annotations

import csv
import json
import re
import unicodedata
from collections import OrderedDict
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTRACTED_DIR = ROOT / "extracted"
RAW_BULLETS_PATH = EXTRACTED_DIR / "raw_bullets.csv"
CONTENT_DIR = ROOT / "content" / "experiences" / "en"
LOG_PATH = EXTRACTED_DIR / "extraction_log.md"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def slugify(value: str, fallback: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^A-Za-z0-9]+", "_", ascii_value).strip("_").lower()
    return slug[:80] or fallback


def yaml_string(value: str) -> str:
    return json.dumps(value or "", ensure_ascii=False)


def yaml_list(values: list[str]) -> str:
    if not values:
        return "[]"
    return "[" + ", ".join(yaml_string(value) for value in values) + "]"


def normalize_key(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip()).lower()


def group_key(row: dict[str, str]) -> tuple[str, str, str, str]:
    return (
        normalize_key(row["section_name"]),
        normalize_key(row["experience_title"]),
        normalize_key(row["organization"]),
        normalize_key(row["date"]),
    )


def source_reference(row: dict[str, str]) -> dict[str, str]:
    return {
        "original_zip_name": row["original_zip_name"],
        "source_project": row["source_project"],
        "source_project_zip": row["source_project_zip"],
        "source_tex_file": row["source_tex_file"],
        "source_line_number": row["source_line_number"],
    }


def write_reference(handle, reference: dict[str, str], indent: str = "  ") -> None:
    handle.write(f"{indent}- original_zip_name: {yaml_string(reference['original_zip_name'])}\n")
    handle.write(f"{indent}  source_project: {yaml_string(reference['source_project'])}\n")
    handle.write(f"{indent}  source_project_zip: {yaml_string(reference['source_project_zip'])}\n")
    handle.write(f"{indent}  source_tex_file: {yaml_string(reference['source_tex_file'])}\n")
    handle.write(f"{indent}  source_line_number: {yaml_string(reference['source_line_number'])}\n")


def main() -> int:
    if not RAW_BULLETS_PATH.exists():
        raise SystemExit(f"Missing {RAW_BULLETS_PATH}. Run scripts/extract_from_tex.py first.")

    CONTENT_DIR.mkdir(parents=True, exist_ok=True)
    rows = read_csv(RAW_BULLETS_PATH)
    groups: OrderedDict[tuple[str, str, str, str], list[dict[str, str]]] = OrderedDict()
    for row in rows:
        groups.setdefault(group_key(row), []).append(row)

    used_ids: set[str] = set()
    files_written = 0

    for group_index, (_, group_rows) in enumerate(groups.items(), start=1):
        first = group_rows[0]
        title = first["experience_title"] or "Untitled Experience"
        base_id = slugify(
            "_".join(
                part
                for part in [
                    first["section_name"],
                    first["experience_title"],
                    first["organization"],
                    first["date"],
                ]
                if part
            ),
            f"experience_{group_index:03d}",
        )
        experience_id = base_id
        suffix = 2
        while experience_id in used_ids:
            experience_id = f"{base_id}_{suffix}"
            suffix += 1
        used_ids.add(experience_id)

        bullet_groups: OrderedDict[str, list[dict[str, str]]] = OrderedDict()
        for row in group_rows:
            bullet_groups.setdefault(row["bullet_text"], []).append(row)

        tools = sorted(
            {
                tool.strip()
                for row in group_rows
                for tool in row["detected_tools"].split(";")
                if tool.strip()
            }
        )

        yaml_path = CONTENT_DIR / f"{experience_id}.yaml"
        with yaml_path.open("w", encoding="utf-8") as handle:
            handle.write(f"experience_id: {yaml_string(experience_id)}\n")
            handle.write("status: needs_review\n")
            handle.write(f"section_type: {yaml_string(first['section_name'])}\n")
            handle.write(f"title_en: {yaml_string(title)}\n")
            handle.write(f"organization_en: {yaml_string(first['organization'])}\n")
            handle.write('location: ""\n')
            handle.write(f"date: {yaml_string(first['date'])}\n")
            handle.write("role_fit: []\n")
            handle.write(f"tools: {yaml_list(tools)}\n")
            handle.write("source_references:\n")
            seen_refs: set[tuple[str, str, str, str, str]] = set()
            for row in group_rows:
                ref = source_reference(row)
                ref_key = tuple(ref.values())
                if ref_key in seen_refs:
                    continue
                seen_refs.add(ref_key)
                write_reference(handle, ref)
            handle.write("bullets:\n")
            for bullet_index, (bullet_text, rows_for_bullet) in enumerate(bullet_groups.items(), start=1):
                bullet_id = f"{experience_id}_b{bullet_index:03d}"
                handle.write(f"  - bullet_id: {yaml_string(bullet_id)}\n")
                handle.write("    status: needs_review\n")
                handle.write(f"    text_en: {yaml_string(bullet_text)}\n")
                handle.write('    text_zh: ""\n')
                handle.write("    tags:\n")
                handle.write("      role: []\n")
                handle.write("      skills: []\n")
                handle.write("      keywords: []\n")
                handle.write("    source_references:\n")
                for row in rows_for_bullet:
                    write_reference(handle, source_reference(row), indent="      ")
        files_written += 1

    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write("\n## YAML Generation\n\n")
        handle.write(f"Generated: {datetime.now().isoformat(timespec='seconds')}\n\n")
        handle.write(f"- Conservative experience groups: {len(groups)}\n")
        handle.write(f"- YAML files written: {files_written}\n")
        handle.write("- Every generated YAML file uses `status: needs_review`.\n")

    print(f"Conservative experience groups: {len(groups)}")
    print(f"YAML files written: {files_written}")
    print(f"Wrote files under {CONTENT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
