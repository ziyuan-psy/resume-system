from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

try:
    from scripts import phase6a_jd_intake as phase6a
    from scripts import phase6b_content_selection as phase6b
    from scripts.library_yaml import find_value, parse_entry_segments, parse_nested_list
except ImportError:  # pragma: no cover - supports running from scripts/
    import phase6a_jd_intake as phase6a
    import phase6b_content_selection as phase6b
    from library_yaml import find_value, parse_entry_segments, parse_nested_list


ROOT = Path(__file__).resolve().parents[1]
CONTACTS_DIR = Path("content") / "profile" / "contacts"
TEMPLATE_PATH = Path("templates") / "us_resume_template.tex"
SELECTION_DIR = Path("generated") / "selection"
TEX_DIR = Path("generated") / "tex"
ENGLISH_CONTACT_PROFILES = {"us_en", "china_intl_en"}
RESERVED_CHINESE_CONTACT_PROFILE = "china_domestic_zh"

ANCHORS = {
    "header": ("RESUME_HEADER_START", "RESUME_HEADER_END"),
    "education": ("EDUCATION_START", "EDUCATION_END"),
    "professional": ("PROFESSIONAL_EXPERIENCE_START", "PROFESSIONAL_EXPERIENCE_END"),
    "selected": ("SELECTED_EXPERIENCE_SECTION_START", "SELECTED_EXPERIENCE_SECTION_END"),
    "skills": ("SKILLS_START", "SKILLS_END"),
}

FORBIDDEN_TEX_MARKERS = [
    "content/archive",
    "extracted/raw_",
    "raw_overleaf_exports",
    "source_pool_ids",
    "raw_bullet_ids",
    "source_references",
    "Source candidate text",
    "Duplicate count",
    "Source reference count",
    "Selection JSON",
]


class Phase6CError(Exception):
    pass


@dataclass(frozen=True)
class Phase6CPaths:
    selection_path: Path
    template_path: Path
    contact_path: Path
    tex_path: Path


def ensure_path_under(root: Path, path: Path) -> None:
    root_resolved = root.resolve()
    path_resolved = path.resolve()
    try:
        path_resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise Phase6CError(f"Refusing to use a path outside project root: {path}") from exc


def contact_profile_path(root: Path, contact_profile: str) -> Path:
    if contact_profile == RESERVED_CHINESE_CONTACT_PROFILE:
        raise Phase6CError(
            "Contact profile china_domestic_zh is reserved for a future Chinese resume workflow. "
            "The English Phase 6C renderer supports only: china_intl_en, us_en."
        )
    if contact_profile not in ENGLISH_CONTACT_PROFILES:
        raise Phase6CError(
            f"Unknown English contact profile: {contact_profile}. "
            "Supported English contact profiles: china_intl_en, us_en."
        )
    return root / CONTACTS_DIR / f"{contact_profile}.yaml"


def build_paths(root: Path, slug: str, contact_profile: str) -> Phase6CPaths:
    paths = Phase6CPaths(
        selection_path=root / SELECTION_DIR / f"{slug}_selection.json",
        template_path=root / TEMPLATE_PATH,
        contact_path=contact_profile_path(root, contact_profile),
        tex_path=root / TEX_DIR / f"{slug}.tex",
    )
    for path in paths.__dict__.values():
        ensure_path_under(root, path)
    return paths


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise Phase6CError(f"Selection JSON does not exist: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise Phase6CError("Selection JSON root must be an object.")
    return data


def read_lines(path: Path) -> list[str]:
    if not path.exists():
        raise Phase6CError(f"Required file does not exist: {path}")
    return path.read_text(encoding="utf-8").splitlines()


def parse_contact(path: Path, contact_profile: str) -> dict[str, str]:
    lines = read_lines(path)
    contact = {
        "profile_id": find_value(lines, "profile_id"),
        "profile_label": find_value(lines, "profile_label"),
        "full_name": find_value(lines, "full_name"),
        "email": find_value(lines, "email"),
        "phone": find_value(lines, "phone"),
        "linkedin_display": find_value(lines, "linkedin_display"),
        "linkedin_url": find_value(lines, "linkedin_url"),
        "location": find_value(lines, "location"),
        "language": find_value(lines, "language"),
        "target_market": find_value(lines, "target_market"),
    }
    missing = [key for key, value in contact.items() if not value]
    if missing:
        raise Phase6CError(f"Missing contact fields in {contact_profile}: " + ", ".join(missing))
    if contact["profile_id"] != contact_profile:
        raise Phase6CError(f"Contact profile_id must match requested profile: {contact_profile}")
    if contact["language"] != "en":
        raise Phase6CError(f"English Phase 6C contact profile must use language: en ({contact_profile}).")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", contact["email"]):
        raise Phase6CError(f"Contact email is not valid for {contact_profile}.")
    parsed_url = urlparse(contact["linkedin_url"])
    if parsed_url.scheme != "https" or not parsed_url.netloc or any(char in contact["linkedin_url"] for char in "{} \n\r\t"):
        raise Phase6CError(f"Contact LinkedIn URL must be a safe https URL for {contact_profile}.")
    return contact


def parse_coursework(root: Path) -> list[dict[str, object]]:
    path = root / phase6b.COURSEWORK_PATH
    lines = read_lines(path)
    entries = []
    for start, end in parse_entry_segments(lines, "coursework_id"):
        segment = lines[start:end]
        entries.append(
            {
                "coursework_id": find_value(segment, "coursework_id"),
                "title_en": find_value(segment, "title_en"),
                "education_ids": parse_nested_list(segment, "education_ids"),
            }
        )
    return entries


def latex_escape(value: object) -> str:
    text = str(value)
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
        "–": "--",
        "—": "---",
        "’": "'",
        "“": "``",
        "”": "''",
    }
    return "".join(replacements.get(char, char) for char in text)


def anchor_line(marker: str) -> str:
    return rf"^\s*%\s*{re.escape(marker)}\s*$"


def validate_template_anchors(template: str) -> None:
    for start_marker, end_marker in ANCHORS.values():
        start_count = len(re.findall(anchor_line(start_marker), template, flags=re.MULTILINE))
        end_count = len(re.findall(anchor_line(end_marker), template, flags=re.MULTILINE))
        if start_count != 1 or end_count != 1:
            raise Phase6CError(f"Template anchor pair must appear exactly once: {start_marker} / {end_marker}")


def replace_anchor(template: str, start_marker: str, end_marker: str, body: str) -> str:
    pattern = re.compile(
        rf"(?ms)^([ \t]*%\s*{re.escape(start_marker)}\s*)$.*?^([ \t]*%\s*{re.escape(end_marker)}\s*)$"
    )
    replaced, count = pattern.subn(lambda match: f"{match.group(1)}\n{body.rstrip()}\n{match.group(2)}", template)
    if count != 1:
        raise Phase6CError(f"Could not replace template anchor pair: {start_marker} / {end_marker}")
    return replaced


def remove_optional_placeholder_sections(tex: str) -> str:
    return re.sub(r"\n\s*% Optional section: Awards.*?(?=\n\\end\{document\})", "\n", tex, flags=re.DOTALL)


def replace_metadata_placeholders(tex: str, contact: dict[str, str]) -> str:
    full_name = latex_escape(contact["full_name"])
    tex = tex.replace("pdftitle={[Full Name] Resume}", f"pdftitle={{{full_name} Resume}}")
    tex = tex.replace("pdfauthor={[Full Name]}", f"pdfauthor={{{full_name}}}")
    return tex


def source_pool_index(experiences: dict[str, dict[str, object]]) -> dict[str, set[str]]:
    return {
        experience_id: {str(pool["pool_id"]) for pool in phase6b.pool_index_for_experience(experience).values()}
        for experience_id, experience in experiences.items()
    }


def validate_selection(
    selection: dict[str, Any],
    slug: str,
    experiences: dict[str, dict[str, object]],
    skills: dict[str, dict[str, object]],
    coursework: dict[str, dict[str, object]],
    education: dict[str, dict[str, object]],
    expected_library_fingerprint: str,
) -> None:
    phase6b.validate_selection_json(
        selection,
        slug,
        experiences,
        skills,
        coursework,
        expected_library_fingerprint=expected_library_fingerprint,
        require_display_titles=False,
    )
    if "education_display_rules" not in selection:
        raise Phase6CError("Selection JSON is missing education_display_rules. Re-run Phase 6B first.")

    education_rule_entries = selection["education_display_rules"].get("entries")
    if not isinstance(education_rule_entries, list):
        raise Phase6CError("education_display_rules.entries must be a list.")
    for entry in education_rule_entries:
        if not isinstance(entry, dict):
            raise Phase6CError("Each education display rule entry must be an object.")
        education_id = entry.get("education_id")
        if education_id not in education:
            raise Phase6CError(f"Unknown education_id in education_display_rules: {education_id}")

    section_plan = selection["resume_section_plan"]
    non_work_section = section_plan["non_work_section_title"]
    for item in selection["experience_selections"]:
        target_section = item["target_section"]
        if target_section != "Professional Experience" and target_section != non_work_section:
            raise Phase6CError(f"Experience {item['experience_id']} target_section is inconsistent with resume_section_plan.")
        experience_id = str(item["experience_id"])
        phase6b.resolve_display_title(
            item,
            experiences[experience_id],
            f"experience selection {experience_id}",
            require_display_title=False,
        )


def selected_coursework_by_education(selection: dict[str, Any], coursework: dict[str, dict[str, object]]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for item in selection["coursework_selections"]["recommended_final_display"]:
        coursework_id = str(item["coursework_id"])
        course = coursework[coursework_id]
        title = str(course["title_en"])
        for education_id in course["education_ids"]:  # type: ignore[index]
            grouped.setdefault(str(education_id), []).append(title)
    return grouped


def included_education_entries(
    selection: dict[str, Any],
    education_by_id: dict[str, dict[str, object]],
) -> list[tuple[dict[str, Any], dict[str, object]]]:
    included = []
    for rule in selection["education_display_rules"]["entries"]:
        if not rule.get("include_by_default"):
            continue
        education_id = str(rule["education_id"])
        included.append((rule, education_by_id[education_id]))
    return included


def render_header(contact: dict[str, str]) -> str:
    return f"""    \\begin{{header}}
        \\fontsize{{25 pt}}{{25 pt}}\\selectfont {latex_escape(contact["full_name"])}

        \\vspace{{5 pt}}

        \\normalsize
        \\mbox{{\\hrefWithoutArrow{{mailto:{contact["email"]}}}{{{latex_escape(contact["email"])}}}}}%
        \\kern 5.0 pt%
        \\AND%
        \\kern 5.0 pt%
        \\mbox{{{latex_escape(contact["phone"])}}}%
        \\kern 5.0 pt%
        \\AND%
        \\kern 5.0 pt%
        \\mbox{{\\hrefWithoutArrow{{{contact["linkedin_url"]}}}{{{latex_escape(contact["linkedin_display"])}}}}}%
        \\kern 5.0 pt%
        \\AND%
        \\kern 5.0 pt%
        \\mbox{{{latex_escape(contact["location"])}}}%
    \\end{{header}}"""


def join_heading_parts(primary: object, secondary: object = "", location: object = "") -> str:
    parts = [latex_escape(primary)]
    if str(secondary).strip():
        parts.append(latex_escape(secondary))
    text = ", ".join(parts)
    if str(location).strip():
        text += f" -- {latex_escape(location)}"
    return text


def render_education_heading(item: dict[str, object]) -> str:
    degree = str(item["degree_en"])
    if item.get("gpa_display"):
        degree = f"{degree} ({item['gpa_en']})"
    location = item["location"] if item.get("location_display", True) else ""
    return f"\\textbf{{{latex_escape(item['institution_en'])}}}, {join_heading_parts(degree, location=location)}"


def render_education(
    selection: dict[str, Any],
    education_by_id: dict[str, dict[str, object]],
    coursework_by_id: dict[str, dict[str, object]],
) -> str:
    courses_by_education = selected_coursework_by_education(selection, coursework_by_id)
    chunks = ["    \\section{EDUCATION}", ""]
    entries = included_education_entries(selection, education_by_id)
    for index, (rule, item) in enumerate(entries):
        if index:
            chunks.append("    \\vspace{0.2 cm}")
            chunks.append("")
        chunks.append(f"    \\begin{{twocolentry}}{{{latex_escape(item['date'])}}}")
        chunks.append(f"        {render_education_heading(item)}")
        chunks.append("    \\end{twocolentry}")
        education_id = str(item["education_id"])
        course_titles = courses_by_education.get(education_id, [])
        if course_titles and rule.get("display_mode") != "compact":
            chunks.append("")
            chunks.append("    \\vspace{0.10 cm}")
            chunks.append("    \\begin{onecolentry}")
            chunks.append(f"\\textbf{{Coursework:}} {latex_escape(', '.join(course_titles))}")
            chunks.append("    \\end{onecolentry}")
    return "\n".join(chunks)


def render_experience_block(
    selection_item: dict[str, Any],
    experience: dict[str, object],
) -> str:
    bullets = [
        bullet
        for bullet in sorted(selection_item["selected_bullets"], key=lambda value: int(value["global_rank"]))
        if bullet["final_resume_priority"] in {"must_include", "include_if_space"}
    ]
    if not bullets:
        return ""
    display_title = phase6b.resolve_display_title(
        selection_item,
        experience,
        f"experience selection {selection_item['experience_id']}",
        require_display_title=False,
    )
    chunks = [
        f"    \\begin{{twocolentry}}{{{latex_escape(experience['date'])}}}",
        f"        \\textbf{{{latex_escape(display_title)}}}, {join_heading_parts(experience['organization_en'], location=experience['location'])}",
        "    \\end{twocolentry}",
        "",
        "    \\vspace{0.10 cm}",
        "    \\begin{onecolentry}",
        "        \\begin{highlights}",
    ]
    for bullet in bullets:
        chunks.append(f"            \\item {latex_escape(bullet['draft_bullet_text'])}")
    chunks.extend(
        [
            "        \\end{highlights}",
            "    \\end{onecolentry}",
        ]
    )
    return "\n".join(chunks)


def render_experience_section(
    title: str,
    selections: list[dict[str, Any]],
    experiences_by_id: dict[str, dict[str, object]],
) -> str:
    blocks = []
    for item in selections:
        if item["selection_tier"] == "backup":
            continue
        block = render_experience_block(item, experiences_by_id[str(item["experience_id"])])
        if block:
            blocks.append(block)
    if not blocks:
        return ""
    return f"    \\section{{{latex_escape(title.upper())}}}\n\n" + "\n\n    \\vspace{0.2 cm}\n\n".join(blocks)


def split_experience_selections(selection: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    professional = []
    non_work = []
    non_work_title = selection["resume_section_plan"]["non_work_section_title"]
    for item in selection["experience_selections"]:
        if item["selection_tier"] == "backup":
            continue
        if item["target_section"] == "Professional Experience":
            professional.append(item)
        elif item["target_section"] == non_work_title:
            non_work.append(item)
    return professional, non_work


def render_skills(selection: dict[str, Any]) -> str:
    groups: dict[str, list[str]] = {}
    order: list[str] = []
    for item in selection["skill_selections"]["recommended_final_display"]:
        category = str(item["display_category"])
        if category not in groups:
            groups[category] = []
            order.append(category)
        groups[category].append(str(item["display_name"]))

    chunks = ["    \\section{SKILLS}", ""]
    for index, category in enumerate(order):
        if index:
            chunks.append("")
            chunks.append("    \\vspace{0.10 cm}")
        chunks.append("    \\begin{onecolentry}")
        chunks.append(f"        \\textbf{{{latex_escape(category)}:}} {latex_escape(', '.join(groups[category]))}")
        chunks.append("    \\end{onecolentry}")
    return "\n".join(chunks)


def render_tex(
    template: str,
    contact: dict[str, str],
    selection: dict[str, Any],
    education_by_id: dict[str, dict[str, object]],
    coursework_by_id: dict[str, dict[str, object]],
    experiences_by_id: dict[str, dict[str, object]],
) -> str:
    professional, non_work = split_experience_selections(selection)
    non_work_title = str(selection["resume_section_plan"]["non_work_section_title"])
    replacements = {
        "header": render_header(contact),
        "education": render_education(selection, education_by_id, coursework_by_id),
        "professional": render_experience_section("Professional Experience", professional, experiences_by_id),
        "selected": render_experience_section(non_work_title, non_work, experiences_by_id),
        "skills": render_skills(selection),
    }
    tex = template
    for key, body in replacements.items():
        start_marker, end_marker = ANCHORS[key]
        tex = replace_anchor(tex, start_marker, end_marker, body)
    tex = replace_metadata_placeholders(tex, contact)
    return remove_optional_placeholder_sections(tex)


def uncommented_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if not line.lstrip().startswith("%")]


def validate_generated_tex(text: str) -> None:
    live_text = "\n".join(uncommented_lines(text))
    placeholder_pattern = re.compile(
        r"\[[^\]]*(?:placeholder|Full Name|Location|Date Range|Institution|Degree|Program|"
        r"Role Title|Organization|Project|Research Title|Skill Category|Skill \d|Course \d|"
        r"Award|Certification)[^\]]*\]",
        flags=re.IGNORECASE,
    )
    if placeholder_pattern.search(live_text):
        raise Phase6CError("Generated TeX contains live placeholder text.")
    if "Bullet placeholder" in live_text:
        raise Phase6CError("Generated TeX contains live bullet placeholder text.")
    has_project = bool(re.search(r"\\section\{project experience\}", live_text, flags=re.IGNORECASE))
    has_research = bool(re.search(r"\\section\{research experience\}", live_text, flags=re.IGNORECASE))
    if has_project and has_research:
        raise Phase6CError("Generated TeX must not include both Project Experience and Research Experience sections.")
    found = [marker for marker in FORBIDDEN_TEX_MARKERS if marker in live_text]
    if found:
        raise Phase6CError("Generated TeX contains forbidden traceability/source markers: " + ", ".join(found))


def load_inputs(root: Path, slug: str, contact_profile: str) -> tuple[Phase6CPaths, dict[str, Any], dict[str, str], str, dict[str, dict[str, object]], dict[str, dict[str, object]], dict[str, dict[str, object]], dict[str, dict[str, object]]]:
    paths = build_paths(root, slug, contact_profile)
    selection = load_json(paths.selection_path)
    contact = parse_contact(paths.contact_path, contact_profile)
    template = paths.template_path.read_text(encoding="utf-8")
    validate_template_anchors(template)

    education_by_id = phase6b.index_by(phase6b.parse_education(root), "education_id")
    experiences_by_id = phase6b.index_by(phase6b.parse_canonical_experiences(root), "experience_id")
    skills_by_id = phase6b.index_by(phase6b.parse_skills(root), "skill_id")
    coursework_by_id = phase6b.index_by(parse_coursework(root), "coursework_id")
    validate_selection(
        selection,
        slug,
        experiences_by_id,
        skills_by_id,
        coursework_by_id,
        education_by_id,
        phase6b.compute_library_fingerprint(root),
    )
    return paths, selection, contact, template, education_by_id, coursework_by_id, experiences_by_id, skills_by_id


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 6C deterministic LaTeX draft renderer.")
    parser.add_argument("--target-slug", required=True, help="Safe lowercase basename used for selection and generated TeX files.")
    parser.add_argument("--contact-profile", default="us_en", help="English contact profile to render: us_en or china_intl_en.")
    parser.add_argument("--validate-only", action="store_true", help="Validate inputs and an existing generated TeX draft if present, without writing.")
    parser.add_argument("--root", default=str(ROOT), help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def run(args: argparse.Namespace) -> Phase6CPaths:
    root = Path(args.root).resolve()
    slug = phase6a.validate_slug(args.target_slug)
    paths, selection, contact, template, education, coursework, experiences, _skills = load_inputs(root, slug, args.contact_profile)

    if args.validate_only:
        if paths.tex_path.exists():
            validate_generated_tex(paths.tex_path.read_text(encoding="utf-8"))
        return paths

    tex = render_tex(template, contact, selection, education, coursework, experiences)
    validate_generated_tex(tex)
    paths.tex_path.parent.mkdir(parents=True, exist_ok=True)
    paths.tex_path.write_text(tex, encoding="utf-8", newline="\n")
    return paths


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        paths = run(args)
    except (OSError, json.JSONDecodeError, Phase6CError, phase6a.Phase6AError, phase6b.Phase6BError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.validate_only:
        print(f"Phase 6C inputs validated for: {paths.tex_path}")
        if paths.tex_path.exists():
            print("Existing generated TeX validated without writing or overwriting.")
        else:
            print("No generated TeX exists yet; validate-only did not write one.")
    else:
        print(f"LaTeX draft: {paths.tex_path}")
        print(f"Contact profile: {args.contact_profile}")
        print("Phase 6C complete. No PDF was generated or touched.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
