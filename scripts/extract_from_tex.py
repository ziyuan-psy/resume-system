from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTRACTED_DIR = ROOT / "extracted"
MANIFESTS_DIR = EXTRACTED_DIR / "manifests"
RAW_EXPERIENCES_PATH = EXTRACTED_DIR / "raw_experiences.csv"
RAW_BULLETS_PATH = EXTRACTED_DIR / "raw_bullets.csv"
LOG_PATH = EXTRACTED_DIR / "extraction_log.md"

BULLET_ENVS = {"highlights", "highlightsforbulletentries", "itemize"}
TOOL_PATTERNS = [
    ("Copilot Studio", r"\bCopilot Studio\b"),
    ("UT Spark", r"\bUT Spark\b"),
    ("SharePoint", r"\bSharePoint\b"),
    ("Power Automate", r"\bPower\s*Automate\b|\bPowerAutomate\b"),
    ("Power BI", r"\bPower BI\b"),
    ("Tableau", r"\bTableau\b"),
    ("SQL", r"\bSQL\b"),
    ("RAG", r"\bRAG\b"),
    ("LLM", r"\bLLM(?:s)?\b"),
    ("LangChain", r"\bLangChain\b"),
    ("Python", r"\bPython\b"),
    ("R", r"\bR\b"),
    ("Excel", r"\bExcel\b"),
    ("VBA", r"\bVBA\b"),
    ("Figma", r"\bFigma\b"),
    ("MATLAB", r"\bMATLAB\b"),
    ("PsychoPy", r"\bPsychoPy\b"),
    ("Blender", r"\bBlender\b"),
    ("iMotions", r"\biMotions\b"),
    ("Git", r"\bGit\b"),
]


@dataclass
class Heading:
    experience_id: str
    line_number: int
    section_name: str
    title: str
    organization: str
    date: str
    heading_text: str


@dataclass
class PendingBullet:
    line_number: int
    parts: list[str]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def strip_inline_comment(line: str) -> str:
    escaped = False
    for index, char in enumerate(line):
        if char == "\\" and not escaped:
            escaped = True
            continue
        if char == "%" and not escaped:
            return line[:index]
        escaped = False
    return line


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def replace_latex_escapes(value: str) -> str:
    replacements = {
        r"\&": "&",
        r"\%": "%",
        r"\$": "$",
        r"\#": "#",
        r"\_": "_",
        r"\{": "{",
        r"\}": "}",
        r"~": " ",
        r"\textasciitilde{}": "~",
    }
    for source, target in replacements.items():
        value = value.replace(source, target)
    return value


def unwrap_simple_commands(value: str) -> str:
    previous = None
    commands = r"(?:textbf|textit|emph|underline|small|large|hrefWithoutArrow)"
    while previous != value:
        previous = value
        value = re.sub(rf"\\{commands}\{{([^{{}}]*)\}}", r"\1", value)
        value = re.sub(r"\\href\{[^{}]*\}\{([^{}]*)\}", r"\1", value)
    return value


def clean_latex_text(value: str) -> str:
    value = value.replace("\n", " ")
    value = re.sub(r"\\begin\{[^{}]+\}", " ", value)
    value = re.sub(r"\\end\{[^{}]+\}", " ", value)
    value = re.sub(r"\\(?:vspace|hspace|kern|setlength)\*?\{[^{}]*\}", " ", value)
    value = re.sub(r"\\item(?:\s*\[[^\]]*\])?", " ", value)
    value = unwrap_simple_commands(value)
    value = replace_latex_escapes(value)
    value = re.sub(r"\\[A-Za-z@]+(?:\*?)", " ", value)
    value = value.replace("{", " ").replace("}", " ")
    return normalize_space(value)


def parse_section(line: str) -> str | None:
    match = re.search(r"\\section\*?\{([^{}]+)\}", line)
    if not match:
        return None
    return clean_latex_text(match.group(1))


def parse_twocolentry(block_lines: list[str], start_line: int, current_section: str, experience_id: str) -> Heading:
    block = "\n".join(block_lines)
    match = re.search(
        r"\\begin\{twocolentry\}\s*\{(?P<date>.*?)\}\s*(?P<body>.*?)\\end\{twocolentry\}",
        block,
        flags=re.DOTALL,
    )
    date = ""
    body = block
    if match:
        date = clean_latex_text(match.group("date"))
        body = match.group("body")
    title = ""
    organization = ""
    textbf_match = re.search(r"\\textbf\{([^{}]+)\}", body)
    if textbf_match:
        title = clean_latex_text(textbf_match.group(1))
        remainder = body[textbf_match.end() :]
        remainder = re.sub(r"\\end\{twocolentry\}.*", "", remainder, flags=re.DOTALL)
        organization = clean_latex_text(remainder.lstrip(" ,;-"))
    else:
        title = clean_latex_text(re.sub(r"\\end\{twocolentry\}.*", "", body, flags=re.DOTALL))
    heading_text = clean_latex_text(body)
    return Heading(
        experience_id=experience_id,
        line_number=start_line,
        section_name=current_section,
        title=title,
        organization=organization,
        date=date,
        heading_text=heading_text,
    )


def detect_tools(*values: str) -> str:
    haystack = " ".join(value for value in values if value)
    found: list[str] = []
    for label, pattern in TOOL_PATTERNS:
        if re.search(pattern, haystack, flags=re.IGNORECASE):
            found.append(label)
    return "; ".join(found)


def remove_environment_commands(value: str) -> str:
    value = re.sub(r"\\(?:begin|end)\{[^{}]+\}", " ", value)
    return normalize_space(value)


def split_item_segments(active_line: str) -> list[tuple[int, str]]:
    matches = list(re.finditer(r"\\item(?:\s*\[[^\]]*\])?", active_line))
    segments: list[tuple[int, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(active_line)
        segments.append((match.start(), active_line[match.end() : end]))
    return segments


def parse_tex_file(manifest_row: dict[str, str], experience_start_index: int, bullet_start_index: int) -> tuple[list[dict[str, object]], list[dict[str, object]], int, int]:
    tex_path = ROOT / manifest_row["extracted_tex_path"]
    lines = tex_path.read_text(encoding="utf-8-sig").splitlines()
    source_tex_file = manifest_row["source_tex_file"]

    current_section = ""
    current_heading: Heading | None = None
    pending_bullet: PendingBullet | None = None
    env_stack: list[str] = []
    in_document = False
    experiences: list[dict[str, object]] = []
    bullets: list[dict[str, object]] = []
    experience_index = experience_start_index
    bullet_index = bullet_start_index

    def in_bullet_env() -> bool:
        return any(env in BULLET_ENVS for env in env_stack)

    def finalize_bullet() -> None:
        nonlocal pending_bullet, bullet_index
        if pending_bullet is None:
            return
        raw_bullet_tex = normalize_space(" ".join(pending_bullet.parts))
        bullet_text = clean_latex_text(raw_bullet_tex)
        if bullet_text:
            bullet_index += 1
            heading = current_heading
            bullets.append(
                {
                    "bullet_id": f"raw_b{bullet_index:06d}",
                    "original_zip_name": manifest_row["original_zip_name"],
                    "source_project_zip": manifest_row["source_project_zip"],
                    "source_project": manifest_row["source_project"],
                    "source_project_id": manifest_row["source_project_id"],
                    "source_tex_file": source_tex_file,
                    "source_line_number": pending_bullet.line_number,
                    "section_name": heading.section_name if heading else current_section,
                    "experience_id": heading.experience_id if heading else "",
                    "experience_title": heading.title if heading else "",
                    "organization": heading.organization if heading else "",
                    "date": heading.date if heading else "",
                    "bullet_text": bullet_text,
                    "raw_bullet_tex": raw_bullet_tex,
                    "detected_tools": detect_tools(
                        bullet_text,
                        heading.title if heading else "",
                        heading.organization if heading else "",
                    ),
                    "possible_role_tags": "",
                }
            )
        pending_bullet = None

    index = 0
    while index < len(lines):
        line_number = index + 1
        raw_line = lines[index]
        active_line = strip_inline_comment(raw_line)
        stripped = active_line.strip()

        if r"\begin{document}" in stripped:
            in_document = True
        if not in_document:
            index += 1
            continue

        section_name = parse_section(stripped)
        if section_name is not None:
            finalize_bullet()
            current_section = section_name
            current_heading = None
            index += 1
            continue

        if r"\begin{twocolentry}" in stripped:
            finalize_bullet()
            block_lines = [active_line]
            start_line = line_number
            while r"\end{twocolentry}" not in strip_inline_comment(lines[index]) and index + 1 < len(lines):
                index += 1
                block_lines.append(strip_inline_comment(lines[index]))
            experience_index += 1
            current_heading = parse_twocolentry(
                block_lines,
                start_line,
                current_section,
                f"raw_e{experience_index:06d}",
            )
            experiences.append(
                {
                    "experience_id": current_heading.experience_id,
                    "original_zip_name": manifest_row["original_zip_name"],
                    "source_project_zip": manifest_row["source_project_zip"],
                    "source_project": manifest_row["source_project"],
                    "source_project_id": manifest_row["source_project_id"],
                    "source_tex_file": source_tex_file,
                    "heading_line_number": current_heading.line_number,
                    "section_name": current_heading.section_name,
                    "experience_title": current_heading.title,
                    "organization": current_heading.organization,
                    "date": current_heading.date,
                    "heading_text": current_heading.heading_text,
                }
            )
            index += 1
            continue

        begin_envs = re.findall(r"\\begin\{([^{}]+)\}", stripped)
        end_envs = re.findall(r"\\end\{([^{}]+)\}", stripped)

        if in_bullet_env():
            item_segments = split_item_segments(active_line)
            if item_segments:
                for _, segment in item_segments:
                    finalize_bullet()
                    cleaned_segment = remove_environment_commands(segment)
                    pending_bullet = PendingBullet(line_number=line_number, parts=[])
                    if cleaned_segment:
                        pending_bullet.parts.append(cleaned_segment)
            elif pending_bullet is not None:
                continuation = remove_environment_commands(stripped)
                if continuation:
                    pending_bullet.parts.append(continuation)

        for env_name in begin_envs:
            env_stack.append(env_name)
        for env_name in end_envs:
            if env_name in BULLET_ENVS:
                finalize_bullet()
            if env_name in env_stack:
                remove_index = len(env_stack) - 1 - env_stack[::-1].index(env_name)
                del env_stack[remove_index]

        if r"\end{document}" in stripped:
            finalize_bullet()
            in_document = False

        index += 1

    finalize_bullet()
    return experiences, bullets, experience_index, bullet_index


def main() -> int:
    manifest_path = MANIFESTS_DIR / "tex_manifest.csv"
    if not manifest_path.exists():
        raise SystemExit(f"Missing {manifest_path}. Run scripts/unzip_overleaf_exports.py first.")

    manifest_rows = read_csv(manifest_path)
    all_experiences: list[dict[str, object]] = []
    all_bullets: list[dict[str, object]] = []
    experience_index = 0
    bullet_index = 0

    for row in manifest_rows:
        experiences, bullets, experience_index, bullet_index = parse_tex_file(row, experience_index, bullet_index)
        all_experiences.extend(experiences)
        all_bullets.extend(bullets)

    write_csv(
        RAW_EXPERIENCES_PATH,
        all_experiences,
        [
            "experience_id",
            "original_zip_name",
            "source_project_zip",
            "source_project",
            "source_project_id",
            "source_tex_file",
            "heading_line_number",
            "section_name",
            "experience_title",
            "organization",
            "date",
            "heading_text",
        ],
    )
    write_csv(
        RAW_BULLETS_PATH,
        all_bullets,
        [
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
        ],
    )

    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write("\n## Content Extraction\n\n")
        handle.write(f"Generated: {datetime.now().isoformat(timespec='seconds')}\n\n")
        handle.write(f"- TeX manifest rows processed: {len(manifest_rows)}\n")
        handle.write(f"- Raw experience rows: {len(all_experiences)}\n")
        handle.write(f"- Raw active bullet rows: {len(all_bullets)}\n")
        handle.write("- Commented LaTeX bullets were ignored.\n")

    print(f"TeX manifest rows processed: {len(manifest_rows)}")
    print(f"Raw experience rows: {len(all_experiences)}")
    print(f"Raw active bullet rows: {len(all_bullets)}")
    print(f"Wrote {RAW_EXPERIENCES_PATH}")
    print(f"Wrote {RAW_BULLETS_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
