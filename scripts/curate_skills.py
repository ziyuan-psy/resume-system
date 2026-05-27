from __future__ import annotations

import csv
import json
import re
from collections import Counter, OrderedDict, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW_SKILLS_PATH = ROOT / "extracted" / "raw_skills.csv"
PROFILE_SKILLS_PATH = ROOT / "content" / "profile" / "skills.yaml"
SKILL_CATEGORIES_PATH = ROOT / "content" / "taxonomy" / "skill_categories.yaml"

CATEGORY_ORDER = [
    "data_analytics",
    "ai_knowledge_platforms",
    "product_ux_research",
    "research_methods",
    "enterprise_productivity_tools",
    "design_simulation_tools",
    "collaboration_communication",
]

SKILL_CATEGORIES = OrderedDict(
    [
        (
            "data_analytics",
            {
                "display_name": "Data & Analytics",
                "aliases": [
                    "Data & Analytics",
                    "Data & Insights",
                    "Data Analysis",
                    "Data & Reporting",
                    "Data Management& Analytics",
                    "Data Visualization & Reporting",
                    "Languages",
                    "Statistical Software",
                ],
            },
        ),
        (
            "ai_knowledge_platforms",
            {
                "display_name": "AI & Knowledge Platforms",
                "aliases": [
                    "AI & Automation",
                    "AI & Knowledge Platforms",
                    "AI Tools",
                    "AI-Assisted Tools",
                    "Data & AI Systems",
                ],
            },
        ),
        (
            "product_ux_research",
            {
                "display_name": "Product & UX Research",
                "aliases": [
                    "Design & Research",
                    "Product & Collaboration",
                    "Product & UX",
                    "Product Testing & Benchmarking",
                    "Research & Customer Insight",
                    "User Research",
                ],
            },
        ),
        (
            "research_methods",
            {
                "display_name": "Research Methods",
                "aliases": [
                    "Qualitative Methods",
                    "Quantitative Methods",
                    "Research Methods",
                    "Test & Research Methods",
                ],
            },
        ),
        (
            "enterprise_productivity_tools",
            {
                "display_name": "Enterprise & Productivity Tools",
                "aliases": [
                    "Collaboration & Documentation",
                    "Collaboration & Productivity Tools",
                    "Enterprise & Automation Tools",
                    "Enterprise & Productivity Tools",
                    "Knowledge Management & Collaboration",
                    "Knowledge Management & Productivity",
                    "Productivity Tools",
                    "Reporting & Documentation",
                ],
            },
        ),
        (
            "design_simulation_tools",
            {
                "display_name": "Design & Simulation Tools",
                "aliases": [
                    "Design & Simulation",
                    "Lab & Technical Tools",
                    "Technical Tools",
                ],
            },
        ),
        (
            "collaboration_communication",
            {
                "display_name": "Collaboration & Communication",
                "aliases": [
                    "Collaboration & Communication",
                ],
            },
        ),
    ]
)

CATEGORY_ALIAS_TO_ID = {
    alias.lower(): category_id
    for category_id, config in SKILL_CATEGORIES.items()
    for alias in config["aliases"]
}

SKILL_ALIASES = {
    "ai_agent": ("ai_agent", "AI Agent"),
    "ai_agents": ("ai_agent", "AI Agent"),
    "interview": ("interview", "Interview"),
    "interviewing": ("interview", "Interview"),
    "power_automate": ("power_automate", "Power Automate"),
    "powerautomate": ("power_automate", "Power Automate"),
    "power_automation": ("power_automate", "Power Automate"),
}


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


def normalize_id(value: str) -> str:
    value = value.lower()
    value = value.replace("&", "and").replace("+", " plus ")
    value = re.sub(r"\s*\([^)]*\)\s*", " ", value)
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_")


def canonical_skill(row: dict[str, str]) -> tuple[str, str]:
    normalized_key = row["normalized_skill_key"]
    if normalized_key in SKILL_ALIASES:
        return SKILL_ALIASES[normalized_key]
    raw_skill = normalize_space(row["raw_skill_text"])
    return normalize_id(raw_skill), raw_skill


def canonical_category(raw_category: str) -> str:
    return CATEGORY_ALIAS_TO_ID.get(raw_category.lower(), "enterprise_productivity_tools")


def source_reference(row: dict[str, str]) -> dict[str, object]:
    return {
        "raw_skill_id": row["raw_skill_id"],
        "original_zip_name": row["original_zip_name"],
        "source_project": row["source_project"],
        "source_project_zip": row["source_project_zip"],
        "source_project_id": row["source_project_id"],
        "source_tex_file": row["source_tex_file"],
        "source_line_number": int(row["source_line_number"] or 0),
        "raw_category": row["raw_category"],
    }


def unique_values(values: list[str]) -> list[str]:
    seen = set()
    output = []
    for value in values:
        if value not in seen:
            seen.add(value)
            output.append(value)
    return output


def category_sort_key(category_id: str) -> tuple[int, str]:
    try:
        return CATEGORY_ORDER.index(category_id), category_id
    except ValueError:
        return len(CATEGORY_ORDER), category_id


def build_skill_categories() -> dict[str, object]:
    return {
        "skill_categories": [
            {
                "category_id": category_id,
                "display_name": config["display_name"],
                "aliases": config["aliases"],
                "status": "needs_review",
            }
            for category_id, config in SKILL_CATEGORIES.items()
        ]
    }


def build_skills(raw_rows: list[dict[str, str]]) -> list[dict[str, object]]:
    grouped: dict[str, dict[str, object]] = defaultdict(
        lambda: {
            "display_names": Counter(),
            "aliases": [],
            "category_counts": Counter(),
            "raw_category_counts": Counter(),
            "raw_skill_ids": [],
            "source_references": [],
        }
    )

    for row in raw_rows:
        flags = set(filter(None, row.get("parse_flags", "").split(";")))
        if "excluded_interest" in flags:
            continue
        skill_id, display_name = canonical_skill(row)
        raw_category = normalize_space(row["raw_category"])
        category_id = canonical_category(raw_category)
        entry = grouped[skill_id]
        entry["display_names"][display_name] += 1
        entry["aliases"].append(normalize_space(row["raw_skill_text"]))
        entry["category_counts"][category_id] += 1
        entry["raw_category_counts"][(raw_category, category_id)] += 1
        entry["raw_skill_ids"].append(row["raw_skill_id"])
        entry["source_references"].append(source_reference(row))

    skills = []
    for skill_id, entry in grouped.items():
        display_name = entry["display_names"].most_common(1)[0][0]
        category_counts = entry["category_counts"]
        default_category = sorted(
            category_counts,
            key=lambda category_id: (-category_counts[category_id], category_sort_key(category_id)),
        )[0]
        category_variants = [
            {
                "raw_category": raw_category,
                "canonical_category": category_id,
                "count": count,
            }
            for (raw_category, category_id), count in sorted(
                entry["raw_category_counts"].items(),
                key=lambda item: (category_sort_key(item[0][1]), item[0][0].lower()),
            )
        ]
        aliases = unique_values([display_name] + sorted(set(entry["aliases"])))
        skills.append(
            {
                "skill_id": skill_id,
                "display_name": display_name,
                "aliases": aliases,
                "default_category": default_category,
                "category_variants": category_variants,
                "status": "needs_review",
                "raw_skill_ids": unique_values(entry["raw_skill_ids"]),
                "source_references": entry["source_references"],
            }
        )

    return sorted(skills, key=lambda item: (category_sort_key(item["default_category"]), item["display_name"].lower()))


def main() -> int:
    raw_rows = read_csv(RAW_SKILLS_PATH)
    skills = build_skills(raw_rows)
    categories = build_skill_categories()
    write_yaml(PROFILE_SKILLS_PATH, {"skills": skills})
    write_yaml(SKILL_CATEGORIES_PATH, categories)
    excluded = sum(1 for row in raw_rows if "excluded_interest" in row.get("parse_flags", ""))
    print(f"Raw skill rows read: {len(raw_rows)}")
    print(f"Excluded interest rows: {excluded}")
    print(f"Active skills generated: {len(skills)}")
    print(f"Skill categories generated: {len(categories['skill_categories'])}")
    print(f"Wrote {PROFILE_SKILLS_PATH}")
    print(f"Wrote {SKILL_CATEGORIES_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
