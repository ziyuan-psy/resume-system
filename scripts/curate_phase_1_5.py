from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTENT_DIR = ROOT / "content"
INITIAL_YAML_DIR = CONTENT_DIR / "experiences" / "en"
CANONICAL_EN_DIR = CONTENT_DIR / "experiences" / "canonical" / "en"
CANONICAL_ZH_DIR = CONTENT_DIR / "experiences" / "canonical" / "zh"
PROFILE_DIR = CONTENT_DIR / "profile"
TAXONOMY_DIR = CONTENT_DIR / "taxonomy"
ARCHIVE_DIR = CONTENT_DIR / "archive"
RAW_BULLETS_PATH = ROOT / "extracted" / "raw_bullets.csv"
RAW_EXPERIENCES_PATH = ROOT / "extracted" / "raw_experiences.csv"
TEX_MANIFEST_PATH = ROOT / "extracted" / "manifests" / "tex_manifest.csv"
TEX_FILES_DIR = ROOT / "extracted" / "tex_files"
CURATION_REPORT_PATH = CONTENT_DIR / "curation_report.md"
DECISIONS_PATH = ROOT / "DECISIONS.md"


SECTION_MAP = {
    "PROFESSIONAL EXPERIENCE": "professional_experience",
    "RESEARCH EXPERIENCE": "research_experience",
    "PROJECT EXPERIENCE": "project_experience",
    "EXTRACURRICULAR ACTIVITIES": "extracurricular_activities",
}


CANONICAL_EXPERIENCES = OrderedDict(
    [
        (
            "ut_career_ai_systems",
            {
                "canonical": {
                    "title_en": "Graduate Assistant",
                    "organization_en": "AI-Powered Career Systems, UT Career Success",
                    "location": "Austin, TX",
                    "date": "Sep. 2025 - Present",
                    "experience_type": "work",
                },
                "default_section": "professional_experience",
                "match": lambda row: "graduate assistant" in row["experience_title"].lower()
                and "ai-powered career systems" in (
                    row["experience_title"] + " " + row["organization"]
                ).lower(),
                "file_needles": ["graduate_assistant"],
            },
        ),
        (
            "loreal_cognitive_sciences_lab",
            {
                "canonical": {
                    "title_en": "Cognitive Sciences Lab Technician (Contractor)",
                    "organization_en": "L'Oreal R&I Center",
                    "location": "Shanghai",
                    "date": "Jul. 2024 - Jul. 2025",
                    "experience_type": "work",
                },
                "default_section": "professional_experience",
                "match": lambda row: any(
                    token in (row["experience_title"] + " " + row["organization"]).lower()
                    for token in ["l'oreal", "loreal", "evaluation intelligence"]
                ),
                "file_needles": [
                    "l_oreal",
                    "sensory_cognitive",
                    "cognitive_science",
                    "cognitive_technician",
                ],
            },
        ),
        (
            "chinese_academy_engineering_psychology",
            {
                "canonical": {
                    "title_en": "Research Intern",
                    "organization_en": "Lab of Engineering Psychology, Chinese Academy of Sciences",
                    "location": "",
                    "date": "Nov. 2023 - Jun. 2024",
                    "experience_type": "research",
                },
                "default_section": "research_experience",
                "match": lambda row: "engineering psychology" in row["organization"].lower()
                and "chinese academy" in row["organization"].lower(),
                "file_needles": ["engineering_psychology_chines"],
            },
        ),
        (
            "ai_rag_sql_clinical_query_system",
            {
                "canonical": {
                    "title_en": "AI-Powered Data Query System (RAG + SQL) for clinical dataset",
                    "organization_en": "Project Lead",
                    "location": "",
                    "date": "Aug. 2025 - Oct. 2025",
                    "experience_type": "project",
                },
                "default_section": "project_experience",
                "match": lambda row: "ai-powered data query system" in row[
                    "experience_title"
                ].lower(),
                "file_needles": ["ai_powered_data_query_system"],
            },
        ),
        (
            "tennis_performance_dashboard",
            {
                "canonical": {
                    "title_en": "Tennis Performance Dashboard",
                    "organization_en": "Course Project",
                    "location": "",
                    "date": "Aug. 2025 - Nov. 2025",
                    "experience_type": "project",
                },
                "default_section": "project_experience",
                "match": lambda row: any(
                    token in row["experience_title"].lower()
                    for token in ["tennis", "us open", "sports performance dashboard"]
                ),
                "file_needles": ["tennis_performance", "sports_performance", "us_open"],
            },
        ),
        (
            "emotion_perception_thesis",
            {
                "canonical": {
                    "title_en": "The Impact of Continuous or Categorical Thinking on Emotion Perception",
                    "organization_en": "Undergraduate Thesis",
                    "location": "",
                    "date": "Dec. 2023 - May. 2024",
                    "experience_type": "research",
                },
                "default_section": "research_experience",
                "match": lambda row: "continuous or categorical" in row[
                    "experience_title"
                ].lower(),
                "file_needles": ["continuous_or_categorical"],
            },
        ),
        (
            "piggott_internalized_misogyny_scale_revision",
            {
                "canonical": {
                    "title_en": "Chinese Revision of Piggott's (2004) Internalized Misogyny Scale",
                    "organization_en": "Director",
                    "location": "",
                    "date": "Mar. 2022 - Jun. 2022",
                    "experience_type": "research",
                },
                "default_section": "research_experience",
                "match": lambda row: "piggott" in row["experience_title"].lower()
                or "misogyny" in row["experience_title"].lower(),
                "file_needles": ["piggott"],
            },
        ),
        (
            "thrive_health_product_management",
            {
                "canonical": {
                    "title_en": "THRIVE | Health Software Product Management & Prototyping",
                    "organization_en": "Course Project",
                    "location": "",
                    "date": "Jan. 2026 - Apr. 2026",
                    "experience_type": "project",
                },
                "default_section": "project_experience",
                "match": lambda row: "thrive" in row["experience_title"].lower(),
                "file_needles": ["thrive_health"],
            },
        ),
        (
            "judge_assistant_kunshan_court",
            {
                "canonical": {
                    "title_en": "Judge Assistant Intern",
                    "organization_en": "Criminal Trial Division of Kunshan People's Court",
                    "location": "",
                    "date": "Jun. 2022 - Aug. 2022",
                    "experience_type": "work",
                },
                "default_section": "professional_experience",
                "match": lambda row: "judge assistant" in row["experience_title"].lower(),
                "file_needles": ["judge_assistant"],
            },
        ),
        (
            "ai_gpu_portfolio_strategy",
            {
                "canonical": {
                    "title_en": "AI GPU Portfolio Strategy & Scenario Analysis",
                    "organization_en": "Course Project",
                    "location": "",
                    "date": "Oct. 2025 - Dec. 2025",
                    "experience_type": "project",
                },
                "default_section": "project_experience",
                "match": lambda row: "ai gpu portfolio" in row["experience_title"].lower(),
                "file_needles": ["ai_gpu_portfolio"],
            },
        ),
        (
            "gopro_time_series_forecasting",
            {
                "canonical": {
                    "title_en": "Product Performance & Time Series Forecasting - GoPro",
                    "organization_en": "Course Project",
                    "location": "",
                    "date": "Feb. 2026 - Apr. 2026",
                    "experience_type": "project",
                },
                "default_section": "project_experience",
                "match": lambda row: "gopro" in row["experience_title"].lower(),
                "file_needles": ["gopro"],
            },
        ),
    ]
)


COURSEWORK_GROUPS = OrderedDict(
    [
        ("database_management", {"title": "Database Management", "tools": ["SQL", "RAG"]}),
        ("data_storytelling", {"title": "Data Storytelling", "tools": ["Tableau"]}),
        ("product_management", {"title": "Product Management", "tools": []}),
        ("machine_learning_python", {"title": "Machine Learning with Python", "tools": ["Python"]}),
        ("quantifying_ux", {"title": "Quantifying UX", "tools": []}),
        ("ux_prototyping", {"title": "UX Prototyping", "tools": ["Figma"]}),
        ("time_series_forecasting", {"title": "Time Series Forecasting", "tools": []}),
        ("human_factors_engineering", {"title": "Human Factors Engineering", "tools": []}),
        ("psychometrics", {"title": "Psychometrics", "tools": []}),
        ("bayesian_statistics_python", {"title": "Bayesian Statistics with Python", "tools": ["Python"]}),
        ("anatomy_and_physiology", {"title": "Anatomy and Physiology", "tools": []}),
    ]
)


PDF_TOOL_FILES = [
    "project_experience_usability_testing_of_online_pdf_tools_project_lead_apr_2023_j.yaml",
    "research_experience_usability_testing_of_online_pdf_tools_director_apr_2023_jun_.yaml",
    "research_experience_usability_testing_of_online_pdf_tools_project_lead_apr_2023_.yaml",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def json_string(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


def write_yaml(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        emit_yaml(handle, data, 0)


def emit_yaml(handle, value: object, indent: int) -> None:
    space = " " * indent
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                handle.write(f"{space}{key}:\n")
                emit_yaml(handle, item, indent + 2)
            else:
                handle.write(f"{space}{key}: {format_scalar(item)}\n")
    elif isinstance(value, list):
        if not value:
            handle.write(f"{space}[]\n")
            return
        for item in value:
            if isinstance(item, dict):
                handle.write(f"{space}- ")
                first = True
                for key, child in item.items():
                    if first and not isinstance(child, (dict, list)):
                        handle.write(f"{key}: {format_scalar(child)}\n")
                        first = False
                    else:
                        if first:
                            handle.write(f"{key}:\n")
                            first = False
                        else:
                            handle.write(f"{space}  {key}:\n")
                        emit_yaml(handle, child, indent + 4)
            elif isinstance(item, list):
                handle.write(f"{space}-\n")
                emit_yaml(handle, item, indent + 2)
            else:
                handle.write(f"{space}- {format_scalar(item)}\n")
    else:
        handle.write(f"{space}{format_scalar(value)}\n")


def format_scalar(value: object) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return '""'
    if isinstance(value, (int, float)):
        return str(value)
    return json_string(str(value))


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def normalize_match_key(value: str) -> str:
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


def source_ref(row: dict[str, str]) -> dict[str, object]:
    return {
        "raw_bullet_id": row.get("bullet_id", ""),
        "original_zip_name": row.get("original_zip_name", ""),
        "source_project": row.get("source_project", ""),
        "source_project_zip": row.get("source_project_zip", ""),
        "source_project_id": row.get("source_project_id", ""),
        "source_tex_file": row.get("source_tex_file", ""),
        "source_line_number": int(row.get("source_line_number") or 0),
    }


def unique_dicts(items: list[dict[str, object]]) -> list[dict[str, object]]:
    seen = set()
    output = []
    for item in items:
        key = json.dumps(item, sort_keys=True, ensure_ascii=False)
        if key not in seen:
            seen.add(key)
            output.append(item)
    return output


def title_variant(row: dict[str, str]) -> str:
    title = normalize_space(row["experience_title"])
    org = normalize_space(row["organization"])
    if org and org.lower() not in {"course project", "project lead", "director", "undergraduate thesis"}:
        return f"{title}, {org}"
    return title


def quality_flags(text: str, rows: list[dict[str, str]]) -> list[str]:
    flags = []
    lower = f" {text.lower()} "
    if len(text) < 45:
        flags.append("short_fragment")
    if text.endswith(","):
        flags.append("trailing_comma_fragment")
    if " into into " in lower:
        flags.append("repeated_word_into")
    if "\ufffd" in text:
        flags.append("encoding_replacement_char")
    if "\\" in text:
        flags.append("possible_latex_residue")
    if text.count("(") != text.count(")"):
        flags.append("unmatched_parenthesis")
    sections = {row["section_name"] for row in rows if row["section_name"]}
    if len(sections) > 1:
        flags.append("appears_in_multiple_historical_sections")
    return flags


def canonical_id_for_row(row: dict[str, str]) -> str | None:
    if row["section_name"] == "EXTRACURRICULAR ACTIVITIES":
        return None
    if "usability testing of online pdf tools" in row["experience_title"].lower():
        return None
    for experience_id, config in CANONICAL_EXPERIENCES.items():
        if config["match"](row):
            return experience_id
    return None


def build_canonical_experiences(raw_bullets: list[dict[str, str]]) -> tuple[dict[str, object], list[dict[str, str]]]:
    rows_by_id: dict[str, list[dict[str, str]]] = defaultdict(list)
    unresolved = []
    for row in raw_bullets:
        experience_id = canonical_id_for_row(row)
        if experience_id:
            rows_by_id[experience_id].append(row)
        elif row["section_name"] not in {"EXTRACURRICULAR ACTIVITIES"} and "usability testing of online pdf tools" not in row[
            "experience_title"
        ].lower():
            unresolved.append(row)

    canonical_data: dict[str, object] = OrderedDict()
    for experience_id, config in CANONICAL_EXPERIENCES.items():
        rows = rows_by_id.get(experience_id, [])
        grouped: OrderedDict[str, list[dict[str, str]]] = OrderedDict()
        for row in rows:
            grouped.setdefault(normalize_match_key(row["bullet_text"]), []).append(row)

        pools = []
        for index, group_rows in enumerate(grouped.values(), start=1):
            text = group_rows[0]["bullet_text"]
            pools.append(
                {
                    "pool_id": f"{experience_id}_p{index:03d}",
                    "canonical_candidate_text_en": text,
                    "duplicate_count": len(group_rows),
                    "raw_bullet_ids": [row["bullet_id"] for row in group_rows],
                    "quality_flags": quality_flags(text, group_rows),
                    "source_references": unique_dicts([source_ref(row) for row in group_rows]),
                }
            )

        tools = sorted(
            {
                tool.strip()
                for row in rows
                for tool in row.get("detected_tools", "").split(";")
                if tool.strip()
            }
        )
        title_variants = sorted({title_variant(row) for row in rows if row["experience_title"]})
        if config["canonical"]["title_en"] not in title_variants:
            title_variants.insert(0, config["canonical"]["title_en"])
        allowed_sections = sorted(
            {
                SECTION_MAP.get(row["section_name"], row["section_name"].lower().replace(" ", "_"))
                for row in rows
                if row["section_name"]
            }
        )
        if config["default_section"] not in allowed_sections:
            allowed_sections.insert(0, config["default_section"])

        canonical_data[experience_id] = {
            "experience_id": experience_id,
            "status": "needs_review",
            "canonical": config["canonical"],
            "title_variants": title_variants,
            "display_section_rules": {
                "default_section": config["default_section"],
                "allowed_sections": allowed_sections,
            },
            "role_fit": [],
            "tools": tools,
            "skills": [],
            "keywords": [],
            "candidate_bullet_pools": pools,
            "source_references": unique_dicts([source_ref(row) for row in rows]),
        }
    return canonical_data, unresolved


def clean_degree(value: str) -> str:
    value = re.sub(r"\s*\(GPA:[^)]+\)", "", value)
    value = value.replace("Echange student", "Exchange student")
    if value.lower() == "exchange student":
        return "Exchange Student"
    if value.lower() == "publicly-funded exchange student":
        return "Exchange Student"
    return normalize_space(value)


def build_education(raw_experiences: list[dict[str, str]]) -> list[dict[str, object]]:
    education_groups = OrderedDict(
        [
            ("ut_austin_msis", {"institution": "The University of Texas at Austin", "location": "Austin, TX"}),
            ("nanjing_normal_applied_psychology", {"institution": "Nanjing Normal University", "location": ""}),
            ("lingnan_exchange", {"institution": "Lingnan University, Hong Kong", "location": "Hong Kong"}),
        ]
    )
    entries = []
    for education_id, config in education_groups.items():
        rows = [
            row
            for row in raw_experiences
            if row["section_name"] == "EDUCATION" and row["experience_title"] == config["institution"]
        ]
        degree_counts = Counter(clean_degree(row["organization"]) for row in rows if row["organization"])
        date_counts = Counter(normalize_space(row["date"]) for row in rows if row["date"])
        entries.append(
            {
                "education_id": education_id,
                "institution_en": config["institution"],
                "degree_en": degree_counts.most_common(1)[0][0] if degree_counts else "",
                "location": config["location"],
                "date": date_counts.most_common(1)[0][0] if date_counts else "",
                "status": "needs_review",
                "source_references": [
                    {
                        "original_zip_name": row["original_zip_name"],
                        "source_project": row["source_project"],
                        "source_project_zip": row["source_project_zip"],
                        "source_project_id": row["source_project_id"],
                        "source_tex_file": row["source_tex_file"],
                        "source_line_number": int(row["heading_line_number"] or 0),
                    }
                    for row in rows
                ],
            }
        )
    return entries


def load_manifest_by_project_id() -> dict[str, dict[str, str]]:
    if not TEX_MANIFEST_PATH.exists():
        return {}
    return {row["source_project_id"]: row for row in read_csv(TEX_MANIFEST_PATH)}


def normalize_course_item(value: str) -> tuple[str | None, str]:
    variant = normalize_space(value)
    compact = variant.lower()
    if compact.startswith("database management"):
        return "database_management", variant
    if compact.startswith("data storytelling"):
        return "data_storytelling", variant
    if compact.startswith("product management"):
        return "product_management", variant
    if compact.startswith("machine learning with python"):
        return "machine_learning_python", variant
    if compact.startswith("quantifying ux"):
        return "quantifying_ux", variant
    if compact.startswith("ux prototyping"):
        return "ux_prototyping", variant
    if compact.startswith("time series forecasting"):
        return "time_series_forecasting", variant
    if compact.startswith("human factors engineering") or compact.startswith("human factor engineering"):
        return "human_factors_engineering", variant
    if compact.startswith("psychometrics"):
        return "psychometrics", variant
    if compact.startswith("bayesian statistics with python"):
        return "bayesian_statistics_python", variant
    if compact.startswith("anatomy and physiology"):
        return "anatomy_and_physiology", variant
    return None, variant


def clean_coursework_line(line: str) -> str:
    active = line.split("%", 1)[0]
    active = re.sub(r"\\hspace\{[^{}]*\}", " ", active)
    active = re.sub(r"\\textbf\{([^{}]*)\}", r"\1", active)
    active = re.sub(r"\\[A-Za-z]+\{([^{}]*)\}", r"\1", active)
    active = active.replace(r"\&", "&").replace("{", " ").replace("}", " ")
    active = re.sub(r"\\[A-Za-z]+", " ", active)
    active = re.sub(r"\s+", " ", active).strip()
    active = re.sub(r"^(Relevant coursework|Coursework):\s*", "", active, flags=re.I)
    return active


def build_coursework() -> list[dict[str, object]]:
    manifest = load_manifest_by_project_id()
    grouped: dict[str, dict[str, object]] = {
        course_id: {
            "coursework_id": course_id,
            "title_en": config["title"],
            "variants": set(),
            "tags": {"role": [], "tools": config["tools"]},
            "status": "needs_review",
            "source_references": [],
        }
        for course_id, config in COURSEWORK_GROUPS.items()
    }
    for tex_path in sorted(TEX_FILES_DIR.glob("*/main.tex")):
        source_project_id = tex_path.parent.name
        manifest_row = manifest.get(source_project_id, {})
        lines = tex_path.read_text(encoding="utf-8-sig").splitlines()
        for line_number, line in enumerate(lines, start=1):
            if not re.search(r"coursework", line, flags=re.I):
                continue
            cleaned = clean_coursework_line(line)
            for item in [part.strip() for part in cleaned.split(",") if part.strip()]:
                course_id, variant = normalize_course_item(item)
                if not course_id:
                    continue
                grouped[course_id]["variants"].add(variant)
                grouped[course_id]["source_references"].append(
                    {
                        "original_zip_name": manifest_row.get("original_zip_name", ""),
                        "source_project": manifest_row.get("source_project", ""),
                        "source_project_zip": manifest_row.get("source_project_zip", ""),
                        "source_project_id": source_project_id,
                        "source_tex_file": "main.tex",
                        "source_line_number": line_number,
                    }
                )
    output = []
    for course_id, entry in grouped.items():
        entry["variants"] = sorted(entry["variants"])
        entry["source_references"] = unique_dicts(entry["source_references"])
        output.append(entry)
    return output


def initial_yaml_file_names() -> list[str]:
    if not INITIAL_YAML_DIR.exists():
        return []
    return sorted(path.name for path in INITIAL_YAML_DIR.glob("*.yaml"))


def yaml_groups_for_experience(files: list[str], experience_id: str) -> list[str]:
    needles = CANONICAL_EXPERIENCES[experience_id]["file_needles"]
    return [name for name in files if any(needle in name for needle in needles)]


def archive_plan(files: list[str]) -> tuple[list[str], list[str], list[str]]:
    pdf_tools = [name for name in files if name in PDF_TOOL_FILES]
    extracurricular = [name for name in files if name.startswith("extracurricular_activities_")]
    canonical_related = set(pdf_tools + extracurricular)
    remaining = [name for name in files if name not in canonical_related]
    return pdf_tools, extracurricular, remaining


def write_decisions() -> None:
    DECISIONS_PATH.write_text(
        """# Decisions

## Phase 1.5 Content Curation

- Raw extracted content is immutable. `extracted/raw_bullets.csv` and `extracted/raw_experiences.csv` are traceability data and must not be rewritten during curation.
- Education is managed separately from experience content in `content/profile/education.yaml`.
- Coursework is dynamic profile metadata in `content/profile/coursework.yaml`, not part of fixed education entries.
- Extracurricular content is archived by default.
- Usability Testing of Online PDF Tools is excluded from active content.
- Section is display logic, not an identity attribute for canonical experiences.
- Canonical experiences preserve historical title variants in `title_variants`.
- Archive content must be excluded from default resume generation.
- Canonical bullets must come from extracted content or user-approved content only.
""",
        encoding="utf-8",
    )


def write_readme_phase_section() -> None:
    readme = ROOT / "README.md"
    text = readme.read_text(encoding="utf-8")
    marker = "## Phase 1.5 Content Curation\n"
    section = """\n---\n\n## Phase 1.5 Content Curation\n\nThe MVP extraction phase is complete. The repository now separates resume data into layers:\n\n- `extracted/` is the immutable traceability layer generated from historical Overleaf exports.\n- `content/experiences/canonical/` is the active curated experience library for future resume generation.\n- `content/profile/education.yaml` stores fixed school, degree, date, and location information only.\n- `content/profile/coursework.yaml` stores selectable coursework metadata for future job-specific resumes.\n- `content/archive/` preserves excluded or superseded content and must not be used by default generation.\n\nPhase 1.5 focuses on canonical grouping, candidate bullet pools, title variants, archive decisions, and profile separation. It does not rewrite bullets or generate tailored resumes.\n"""
    if marker not in text:
        readme.write_text(text.rstrip() + section + "\n", encoding="utf-8")


def write_taxonomy_files() -> None:
    TAXONOMY_DIR.mkdir(parents=True, exist_ok=True)
    for name, key in [
        ("role_tags.yaml", "role_tags"),
        ("skill_tags.yaml", "skill_tags"),
        ("tool_tags.yaml", "tool_tags"),
        ("keyword_tags.yaml", "keyword_tags"),
    ]:
        write_yaml(TAXONOMY_DIR / name, {key: [], "status": "needs_review"})


def write_curation_report(
    canonical_data: dict[str, object],
    education_entries: list[dict[str, object]],
    coursework_entries: list[dict[str, object]],
    unresolved: list[dict[str, str]],
    files: list[str],
) -> None:
    pdf_tools, extracurricular, remaining = archive_plan(files)
    with CURATION_REPORT_PATH.open("w", encoding="utf-8") as handle:
        handle.write("# Phase 1.5 Curation Report\n\n")
        handle.write(f"Generated: {datetime.now().isoformat(timespec='seconds')}\n\n")
        handle.write("## Summary\n\n")
        handle.write(f"- Canonical experience files generated: {len(canonical_data)}\n")
        handle.write(f"- Education entries generated: {len(education_entries)}\n")
        handle.write(f"- Coursework entries generated: {len(coursework_entries)}\n")
        handle.write(f"- Initial YAML files planned for archive: {len(files)}\n")
        handle.write(f"- Files excluded from active generation: {len(pdf_tools) + len(extracurricular)}\n")
        handle.write(f"- Unresolved raw bullet rows: {len(unresolved)}\n\n")
        handle.write("## Canonical Merges\n\n")
        for experience_id in canonical_data:
            groups = yaml_groups_for_experience(files, experience_id)
            handle.write(f"### {experience_id}\n\n")
            if groups:
                for name in groups:
                    handle.write(f"- {name}\n")
            else:
                handle.write("- No initial YAML group found; generated from raw rows only.\n")
            handle.write("\n")
        handle.write("## Archived Files\n\n")
        handle.write("### Excluded: Usability Testing of Online PDF Tools\n\n")
        for name in pdf_tools:
            handle.write(f"- content/archive/excluded/usability_testing_online_pdf_tools/{name}\n")
        handle.write("\n### Extracurricular\n\n")
        for name in extracurricular:
            handle.write(f"- content/archive/extracurricular/{name}\n")
        handle.write("\n### MVP Initial Experiences\n\n")
        for name in remaining:
            handle.write(f"- content/archive/mvp_initial_experiences/en/{name}\n")
        handle.write("\n## Excluded From Active Generation\n\n")
        for name in pdf_tools + extracurricular:
            handle.write(f"- {name}\n")
        handle.write("\n## Unresolved Or Uncertain Groups\n\n")
        if not unresolved:
            handle.write("- None at file-cluster level. All canonical content remains `needs_review`.\n")
        else:
            grouped = Counter((row["experience_title"], row["organization"]) for row in unresolved)
            for (title, org), count in grouped.most_common():
                handle.write(f"- {title} | {org}: {count} raw bullet rows\n")


def generate() -> None:
    raw_bullets = read_csv(RAW_BULLETS_PATH)
    raw_experiences = read_csv(RAW_EXPERIENCES_PATH)
    initial_files = initial_yaml_file_names()

    CANONICAL_EN_DIR.mkdir(parents=True, exist_ok=True)
    CANONICAL_ZH_DIR.mkdir(parents=True, exist_ok=True)
    (CANONICAL_ZH_DIR / ".gitkeep").write_text("", encoding="utf-8")
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    CONTENT_DIR.mkdir(parents=True, exist_ok=True)

    canonical_data, unresolved = build_canonical_experiences(raw_bullets)
    for experience_id, data in canonical_data.items():
        write_yaml(CANONICAL_EN_DIR / f"{experience_id}.yaml", data)

    education_entries = build_education(raw_experiences)
    write_yaml(PROFILE_DIR / "education.yaml", {"education": education_entries})

    coursework_entries = build_coursework()
    write_yaml(PROFILE_DIR / "coursework.yaml", {"coursework": coursework_entries})

    write_taxonomy_files()
    write_decisions()
    write_readme_phase_section()
    write_curation_report(canonical_data, education_entries, coursework_entries, unresolved, initial_files)

    print(f"Canonical experience files generated: {len(canonical_data)}")
    print(f"Education entries generated: {len(education_entries)}")
    print(f"Coursework entries generated: {len(coursework_entries)}")
    print(f"Curation report: {CURATION_REPORT_PATH}")


def mark_archive_file(path: Path, status: str, reason: str) -> None:
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"^status: .*$", f"status: {status}", text, count=1, flags=re.M)
    if "exclude_from_generation:" not in text:
        text = re.sub(
            r"^(status: .*)$",
            "\\1\nexclude_from_generation: true",
            text,
            count=1,
            flags=re.M,
        )
    if "archive_reason:" not in text:
        text = re.sub(
            r"^(exclude_from_generation: true)$",
            f'\\1\narchive_reason: {json_string(reason)}',
            text,
            count=1,
            flags=re.M,
        )
    path.write_text(text, encoding="utf-8")


def mark_archives() -> None:
    excluded_dir = ARCHIVE_DIR / "excluded" / "usability_testing_online_pdf_tools"
    extracurricular_dir = ARCHIVE_DIR / "extracurricular"
    mvp_dir = ARCHIVE_DIR / "mvp_initial_experiences" / "en"

    for path in sorted(excluded_dir.glob("*.yaml")):
        mark_archive_file(path, "excluded", "Excluded from active generation by Phase 1.5 decision.")
    for path in sorted(extracurricular_dir.glob("*.yaml")):
        mark_archive_file(path, "archived", "Extracurricular content is archived by default.")
    for path in sorted(mvp_dir.glob("*.yaml")):
        mark_archive_file(path, "archived", "Superseded by Phase 1.5 canonical experience files.")

    print("Archive metadata updated.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mark-archives", action="store_true")
    args = parser.parse_args()
    if args.mark_archives:
        mark_archives()
    else:
        generate()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
