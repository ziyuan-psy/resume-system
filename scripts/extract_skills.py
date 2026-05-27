from __future__ import annotations

import csv
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEX_FILES_DIR = ROOT / "extracted" / "tex_files"
TEX_MANIFEST_PATH = ROOT / "extracted" / "manifests" / "tex_manifest.csv"
RAW_SKILLS_PATH = ROOT / "extracted" / "raw_skills.csv"

FIELDNAMES = [
    "raw_skill_id",
    "original_zip_name",
    "source_project",
    "source_project_zip",
    "source_project_id",
    "source_tex_file",
    "source_line_number",
    "source_entry_start_line",
    "source_entry_end_line",
    "section_name",
    "raw_category",
    "raw_skill_text",
    "raw_entry_text",
    "normalized_skill_key",
    "parse_flags",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_manifest_by_project_id() -> dict[str, dict[str, str]]:
    if not TEX_MANIFEST_PATH.exists():
        return {}
    return {row["source_project_id"]: row for row in read_csv(TEX_MANIFEST_PATH)}


def active_line(line: str) -> str:
    return line.split("%", 1)[0]


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def strip_latex(value: str) -> str:
    value = value.replace(r"\&", "&")
    value = re.sub(r"\\hspace\{[^{}]*\}", " ", value)
    value = re.sub(r"\\vspace\{[^{}]*\}", " ", value)
    value = re.sub(r"\\begin\{[^{}]*\}", " ", value)
    value = re.sub(r"\\end\{[^{}]*\}", " ", value)
    value = re.sub(r"\\textbf\{([^{}]*)\}", r"\1", value)
    value = re.sub(r"\\[A-Za-z]+\{([^{}]*)\}", r"\1", value)
    value = value.replace("{", " ").replace("}", " ")
    value = re.sub(r"\\[A-Za-z]+", " ", value)
    value = value.replace("\\", " ")
    return normalize_space(value)


def section_name_from_line(line: str) -> str | None:
    match = re.search(r"\\section\{([^{}]+)\}", active_line(line))
    if not match:
        return None
    return normalize_space(match.group(1)).upper()


def split_outside_parentheses(value: str) -> list[str]:
    output: list[str] = []
    buffer: list[str] = []
    depth = 0
    for char in value:
        if char == "(":
            depth += 1
        elif char == ")" and depth:
            depth -= 1
        if char == "," and depth == 0:
            item = normalize_space("".join(buffer))
            if item:
                output.append(item)
            buffer = []
            continue
        buffer.append(char)
    item = normalize_space("".join(buffer))
    if item:
        output.append(item)
    return output


def normalized_skill_key(value: str) -> str:
    value = strip_latex(value).lower()
    value = value.replace("&", "and")
    value = re.sub(r"\s*\([^)]*\)\s*", " ", value)
    value = re.sub(r"[^a-z0-9+#.]+", "_", value)
    return value.strip("_")


def parse_skill_entry(block: list[tuple[int, str]]) -> tuple[str, str, str] | None:
    joined = " ".join(active for _, active in block)
    match = re.search(
        r"\\textbf\{([^{}:]+):\}\s*(.*?)(?:\\end\{onecolentry\}|$)",
        joined,
    )
    if not match:
        match = re.search(
            r"\\textbf\{([^{}]+)\}\s*(.*?)(?:\\end\{onecolentry\}|$)",
            joined,
        )
    if not match:
        return None
    raw_category = strip_latex(match.group(1))
    raw_skill_text = strip_latex(match.group(2))
    raw_entry_text = strip_latex(joined)
    return raw_category, raw_skill_text, raw_entry_text


def parse_tex_file(path: Path, manifest_row: dict[str, str]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    in_skills = False
    in_onecolentry = False
    block: list[tuple[int, str]] = []
    block_start = 0

    for line_number, line in enumerate(lines, start=1):
        active = active_line(line)
        section_name = section_name_from_line(line)
        if section_name:
            in_skills = section_name == "SKILLS"
            in_onecolentry = False
            block = []
            block_start = 0
            continue

        if not in_skills:
            continue

        if r"\begin{onecolentry}" in active:
            in_onecolentry = True
            block = []
            block_start = line_number

        if in_onecolentry:
            block.append((line_number, active))

        if in_onecolentry and r"\end{onecolentry}" in active:
            parsed = parse_skill_entry(block)
            block_end = line_number
            in_onecolentry = False
            if not parsed:
                block = []
                block_start = 0
                continue
            raw_category, raw_skill_text, raw_entry_text = parsed
            category_lower = raw_category.lower()
            for item in split_outside_parentheses(raw_skill_text):
                flags = []
                if ";" in item:
                    flags.append("semicolon_present")
                if category_lower == "interests":
                    flags.append("excluded_interest")
                rows.append(
                    {
                        "original_zip_name": manifest_row.get("original_zip_name", ""),
                        "source_project": manifest_row.get("source_project", ""),
                        "source_project_zip": manifest_row.get("source_project_zip", ""),
                        "source_project_id": path.parent.name,
                        "source_tex_file": "main.tex",
                        "source_line_number": block_start,
                        "source_entry_start_line": block_start,
                        "source_entry_end_line": block_end,
                        "section_name": "SKILLS",
                        "raw_category": raw_category,
                        "raw_skill_text": item,
                        "raw_entry_text": raw_entry_text,
                        "normalized_skill_key": normalized_skill_key(item),
                        "parse_flags": ";".join(flags),
                    }
                )
            block = []
            block_start = 0
    return rows


def main() -> int:
    manifest = load_manifest_by_project_id()
    rows: list[dict[str, object]] = []
    for tex_path in sorted(TEX_FILES_DIR.glob("*/main.tex")):
        manifest_row = manifest.get(tex_path.parent.name, {})
        rows.extend(parse_tex_file(tex_path, manifest_row))

    RAW_SKILLS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with RAW_SKILLS_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        for index, row in enumerate(rows, start=1):
            output = {"raw_skill_id": f"raw_s{index:06d}"}
            output.update(row)
            writer.writerow(output)

    excluded = sum(1 for row in rows if "excluded_interest" in str(row["parse_flags"]))
    print(f"Raw skill rows generated: {len(rows)}")
    print(f"Excluded interest rows: {excluded}")
    print(f"Wrote {RAW_SKILLS_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
