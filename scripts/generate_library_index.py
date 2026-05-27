from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LIBRARY_INDEX_PATH = ROOT / "library_index.md"
PROFILE_DIR = ROOT / "content" / "profile"
EDUCATION_PATH = PROFILE_DIR / "education.yaml"
COURSEWORK_PATH = PROFILE_DIR / "coursework.yaml"
SKILLS_PATH = PROFILE_DIR / "skills.yaml"
SKILL_CATEGORIES_PATH = ROOT / "content" / "taxonomy" / "skill_categories.yaml"
CANONICAL_EN_DIR = ROOT / "content" / "experiences" / "canonical" / "en"
ARCHIVE_DIR = ROOT / "content" / "archive"


def decode_scalar(value: str) -> str:
    value = value.strip()
    if not value or value == "[]":
        return ""
    try:
        return str(json.loads(value))
    except json.JSONDecodeError:
        return value.strip('"')


def find_value(lines: list[str], key: str, start: int = 0, end: int | None = None) -> str:
    end = len(lines) if end is None else end
    pattern = re.compile(rf"^\s*(?:-\s+)?{re.escape(key)}:\s*(.*)$")
    for index in range(start, end):
        match = pattern.match(lines[index])
        if not match:
            continue
        inline = match.group(1).strip()
        if inline:
            return decode_scalar(inline)
        for next_index in range(index + 1, end):
            candidate = lines[next_index].strip()
            if not candidate:
                continue
            if re.match(r"^[A-Za-z_][A-Za-z0-9_]*:", candidate):
                return ""
            return decode_scalar(candidate)
    return ""


def find_block(lines: list[str], key: str) -> tuple[int, int]:
    start = -1
    for index, line in enumerate(lines):
        if re.match(rf"^{re.escape(key)}:\s*$", line):
            start = index + 1
            break
    if start == -1:
        return -1, -1
    end = len(lines)
    for index in range(start, len(lines)):
        if lines[index] and not lines[index].startswith(" "):
            end = index
            break
    return start, end


def parse_list_block(lines: list[str], key: str) -> list[str]:
    start, end = find_block(lines, key)
    if start == -1:
        return []
    values: list[str] = []
    for line in lines[start:end]:
        stripped = line.strip()
        if stripped.startswith("- "):
            values.append(decode_scalar(stripped[2:]))
    return values


def parse_entry_segments(lines: list[str], item_key: str) -> list[tuple[int, int]]:
    starts = [
        index
        for index, line in enumerate(lines)
        if re.match(rf"^\s*-\s+{re.escape(item_key)}:", line)
    ]
    return [(start, starts[pos + 1] if pos + 1 < len(starts) else len(lines)) for pos, start in enumerate(starts)]


def parse_nested_list(segment: list[str], key: str) -> list[str]:
    start = -1
    base_indent = 0
    for index, line in enumerate(segment):
        match = re.match(rf"^(\s*){re.escape(key)}:\s*(.*)$", line)
        if match:
            start = index + 1
            base_indent = len(match.group(1))
            if match.group(2).strip() == "[]":
                return []
            break
    if start == -1:
        return []
    values = []
    for line in segment[start:]:
        if line.strip().startswith("- "):
            values.append(decode_scalar(line.strip()[2:]))
            continue
        if line.strip() and len(line) - len(line.lstrip(" ")) <= base_indent:
            break
    return values


def parse_education() -> list[dict[str, str]]:
    if not EDUCATION_PATH.exists():
        return []
    lines = EDUCATION_PATH.read_text(encoding="utf-8").splitlines()
    entries = []
    for start, end in parse_entry_segments(lines, "education_id"):
        segment = lines[start:end]
        entries.append(
            {
                "education_id": find_value(segment, "education_id"),
                "institution_en": find_value(segment, "institution_en"),
                "degree_en": find_value(segment, "degree_en"),
                "location": find_value(segment, "location"),
                "date": find_value(segment, "date"),
                "status": find_value(segment, "status"),
                "source_reference_count": sum(1 for line in segment if "source_project:" in line),
            }
        )
    return entries


def parse_coursework() -> list[dict[str, object]]:
    if not COURSEWORK_PATH.exists():
        return []
    lines = COURSEWORK_PATH.read_text(encoding="utf-8").splitlines()
    entries = []
    for start, end in parse_entry_segments(lines, "coursework_id"):
        segment = lines[start:end]
        entries.append(
            {
                "coursework_id": find_value(segment, "coursework_id"),
                "title_en": find_value(segment, "title_en"),
                "education_ids": parse_nested_list(segment, "education_ids"),
                "variants": parse_nested_list(segment, "variants"),
                "tools": parse_nested_list(segment, "tools"),
                "status": find_value(segment, "status"),
                "source_reference_count": sum(1 for line in segment if "source_project:" in line),
            }
        )
    return entries


def parse_category_variants(segment: list[str]) -> list[dict[str, object]]:
    start = -1
    base_indent = 0
    for index, line in enumerate(segment):
        match = re.match(r"^(\s*)category_variants:\s*$", line)
        if match:
            start = index + 1
            base_indent = len(match.group(1))
            break
    if start == -1:
        return []
    end = len(segment)
    for index in range(start, len(segment)):
        line = segment[index]
        if line.strip() and len(line) - len(line.lstrip(" ")) <= base_indent:
            end = index
            break
    block = segment[start:end]
    variants = []
    for variant_start, variant_end in parse_entry_segments(block, "raw_category"):
        variant = block[variant_start:variant_end]
        variants.append(
            {
                "raw_category": find_value(variant, "raw_category"),
                "canonical_category": find_value(variant, "canonical_category"),
                "count": int(find_value(variant, "count") or 0),
            }
        )
    return variants


def parse_skills() -> list[dict[str, object]]:
    if not SKILLS_PATH.exists():
        return []
    lines = SKILLS_PATH.read_text(encoding="utf-8").splitlines()
    entries = []
    for start, end in parse_entry_segments(lines, "skill_id"):
        segment = lines[start:end]
        raw_skill_ids = parse_nested_list(segment, "raw_skill_ids")
        entries.append(
            {
                "skill_id": find_value(segment, "skill_id"),
                "display_name": find_value(segment, "display_name"),
                "aliases": parse_nested_list(segment, "aliases"),
                "default_category": find_value(segment, "default_category"),
                "category_variants": parse_category_variants(segment),
                "status": find_value(segment, "status"),
                "raw_skill_count": len(raw_skill_ids),
                "source_reference_count": sum(1 for line in segment if "source_project:" in line),
            }
        )
    return entries


def parse_skill_categories() -> dict[str, dict[str, object]]:
    if not SKILL_CATEGORIES_PATH.exists():
        return {}
    lines = SKILL_CATEGORIES_PATH.read_text(encoding="utf-8").splitlines()
    categories = {}
    for start, end in parse_entry_segments(lines, "category_id"):
        segment = lines[start:end]
        category_id = find_value(segment, "category_id")
        categories[category_id] = {
            "category_id": category_id,
            "display_name": find_value(segment, "display_name"),
            "aliases": parse_nested_list(segment, "aliases"),
            "status": find_value(segment, "status"),
        }
    return categories


def parse_candidate_pools(lines: list[str]) -> list[dict[str, object]]:
    start, end = find_block(lines, "candidate_bullet_pools")
    if start == -1:
        return []
    block = lines[start:end]
    pools = []
    for pool_start, pool_end in parse_entry_segments(block, "pool_id"):
        segment = block[pool_start:pool_end]
        pools.append(
            {
                "pool_id": find_value(segment, "pool_id"),
                "text": find_value(segment, "canonical_candidate_text_en"),
                "duplicate_count": int(find_value(segment, "duplicate_count") or 0),
                "raw_bullet_ids": parse_nested_list(segment, "raw_bullet_ids"),
                "quality_flags": parse_nested_list(segment, "quality_flags"),
                "source_reference_count": sum(1 for line in segment if "raw_bullet_id:" in line),
            }
        )
    return pools


def parse_canonical_experience(path: Path) -> dict[str, object]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return {
        "path": path,
        "experience_id": find_value(lines, "experience_id"),
        "status": find_value(lines, "status"),
        "title_en": find_value(lines, "title_en"),
        "organization_en": find_value(lines, "organization_en"),
        "location": find_value(lines, "location"),
        "date": find_value(lines, "date"),
        "experience_type": find_value(lines, "experience_type"),
        "title_variants": parse_list_block(lines, "title_variants"),
        "default_section": find_value(lines, "default_section"),
        "allowed_sections": parse_nested_list(lines, "allowed_sections"),
        "tools": parse_list_block(lines, "tools"),
        "role_fit": parse_list_block(lines, "role_fit"),
        "skills": parse_list_block(lines, "skills"),
        "keywords": parse_list_block(lines, "keywords"),
        "candidate_bullet_pools": parse_candidate_pools(lines),
        "source_reference_count": sum(1 for line in lines if "raw_bullet_id:" in line),
    }


def parse_canonical_experiences() -> list[dict[str, object]]:
    if not CANONICAL_EN_DIR.exists():
        return []
    return [parse_canonical_experience(path) for path in sorted(CANONICAL_EN_DIR.glob("*.yaml"))]


def archive_summary() -> list[tuple[str, int]]:
    if not ARCHIVE_DIR.exists():
        return []
    summaries = []
    for directory in sorted(path for path in ARCHIVE_DIR.rglob("*") if path.is_dir()):
        count = len(list(directory.glob("*.yaml")))
        if count:
            summaries.append((str(directory.relative_to(ROOT)).replace("\\", "/"), count))
    return summaries


def write_list(handle, values: list[str]) -> None:
    if values:
        for value in values:
            handle.write(f"  - {value}\n")
    else:
        handle.write("  - None\n")


def main() -> int:
    education = parse_education()
    coursework = parse_coursework()
    skills = parse_skills()
    skill_categories = parse_skill_categories()
    experiences = parse_canonical_experiences()
    candidate_pool_count = sum(len(exp["candidate_bullet_pools"]) for exp in experiences)

    with LIBRARY_INDEX_PATH.open("w", encoding="utf-8") as handle:
        handle.write("# Resume Library Index\n\n")
        handle.write(f"Generated: {datetime.now().isoformat(timespec='seconds')}\n\n")
        handle.write("This index summarizes the active canonical library. It is generated from `content/profile/education.yaml`, `content/profile/coursework.yaml`, `content/profile/skills.yaml`, and `content/experiences/canonical/en/*.yaml`.\n\n")

        handle.write("## Active Library Summary\n\n")
        handle.write(f"- Education entries: {len(education)}\n")
        handle.write(f"- Coursework entries: {len(coursework)}\n")
        handle.write(f"- Active skills: {len(skills)}\n")
        handle.write(f"- Skill categories: {len(skill_categories)}\n")
        handle.write(f"- Canonical experiences: {len(experiences)}\n")
        handle.write(f"- Candidate bullet pools: {candidate_pool_count}\n")
        handle.write("- Archive content is excluded from default resume generation.\n\n")

        handle.write("## Education\n\n")
        for item in education:
            handle.write(f"### {item['institution_en']}\n\n")
            handle.write(f"- Education ID: `{item['education_id']}`\n")
            handle.write(f"- Degree: {item['degree_en']}\n")
            handle.write(f"- Location: {item['location']}\n")
            handle.write(f"- Date: {item['date']}\n")
            handle.write(f"- Status: {item['status']}\n")
            handle.write(f"- Source references: {item['source_reference_count']}\n\n")

        handle.write("## Coursework\n\n")
        for item in coursework:
            handle.write(f"### {item['title_en']}\n\n")
            handle.write(f"- Coursework ID: `{item['coursework_id']}`\n")
            handle.write(f"- Status: {item['status']}\n")
            handle.write(f"- Education IDs: {', '.join(item['education_ids']) if item['education_ids'] else 'None'}\n")
            handle.write(f"- Tools: {', '.join(item['tools']) if item['tools'] else 'None'}\n")
            handle.write(f"- Source references: {item['source_reference_count']}\n")
            handle.write("- Variants:\n")
            write_list(handle, item["variants"])
            handle.write("\n")

        handle.write("## Skills\n\n")
        if skills:
            skills_by_category: dict[str, list[dict[str, object]]] = {}
            for skill in skills:
                skills_by_category.setdefault(skill["default_category"], []).append(skill)
            for category_id, category_skills in sorted(
                skills_by_category.items(),
                key=lambda item: skill_categories.get(item[0], {}).get("display_name", item[0]),
            ):
                category = skill_categories.get(category_id, {})
                category_name = category.get("display_name", category_id)
                handle.write(f"### {category_name}\n\n")
                handle.write(f"- Category ID: `{category_id}`\n")
                handle.write(f"- Skills: {len(category_skills)}\n")
                handle.write(f"- Category aliases: {', '.join(category.get('aliases', [])) if category.get('aliases') else 'None'}\n\n")
                for skill in sorted(category_skills, key=lambda item: item["display_name"].lower()):
                    aliases = [alias for alias in skill["aliases"] if alias != skill["display_name"]]
                    handle.write(f"- **{skill['display_name']}** (`{skill['skill_id']}`)\n")
                    handle.write(f"  - Status: {skill['status']}\n")
                    handle.write(f"  - Aliases: {', '.join(aliases) if aliases else 'None'}\n")
                    handle.write(f"  - Category variants: {len(skill['category_variants'])}\n")
                    handle.write(f"  - Raw skill rows: {skill['raw_skill_count']}\n")
                    handle.write(f"  - Source references: {skill['source_reference_count']}\n")
                handle.write("\n")
        else:
            handle.write("- No active skills found.\n\n")

        handle.write("## Canonical Experiences\n\n")
        for index, exp in enumerate(experiences, start=1):
            handle.write(f"### {index}. {exp['title_en']}\n\n")
            handle.write(f"- Experience ID: `{exp['experience_id']}`\n")
            handle.write(f"- Status: {exp['status']}\n")
            handle.write(f"- Organization: {exp['organization_en']}\n")
            handle.write(f"- Location: {exp['location']}\n")
            handle.write(f"- Date: {exp['date']}\n")
            handle.write(f"- Type: {exp['experience_type']}\n")
            handle.write(f"- Default section: {exp['default_section']}\n")
            handle.write(f"- Allowed sections: {', '.join(exp['allowed_sections']) if exp['allowed_sections'] else 'None'}\n")
            handle.write(f"- Tools: {', '.join(exp['tools']) if exp['tools'] else 'None'}\n")
            handle.write(f"- Candidate bullet pools: {len(exp['candidate_bullet_pools'])}\n")
            handle.write(f"- Source references: {exp['source_reference_count']}\n")
            handle.write("- Title variants:\n")
            write_list(handle, exp["title_variants"])
            handle.write("\nCandidate bullet pools:\n\n")
            for pool in exp["candidate_bullet_pools"]:
                handle.write(f"- `{pool['pool_id']}` {pool['text']}\n")
                handle.write(f"  - Duplicate count: {pool['duplicate_count']}\n")
                handle.write(f"  - Raw bullet IDs: {', '.join(pool['raw_bullet_ids']) if pool['raw_bullet_ids'] else 'None'}\n")
                handle.write(f"  - Quality flags: {', '.join(pool['quality_flags']) if pool['quality_flags'] else 'None'}\n")
                handle.write(f"  - Source references: {pool['source_reference_count']}\n")
            handle.write("\n")

        handle.write("## Archived / Excluded Content\n\n")
        summaries = archive_summary()
        if summaries:
            for directory, count in summaries:
                handle.write(f"- `{directory}`: {count} YAML files\n")
        else:
            handle.write("- No archived YAML content found.\n")

    print(f"Education entries indexed: {len(education)}")
    print(f"Coursework entries indexed: {len(coursework)}")
    print(f"Skills indexed: {len(skills)}")
    print(f"Skill categories indexed: {len(skill_categories)}")
    print(f"Canonical experiences indexed: {len(experiences)}")
    print(f"Candidate bullet pools indexed: {candidate_pool_count}")
    print(f"Wrote {LIBRARY_INDEX_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
