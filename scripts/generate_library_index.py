from __future__ import annotations

import hashlib
import io
import re
from pathlib import Path
from typing import Any

try:
    from scripts.library_yaml import find_value, parse_entry_segments, parse_nested_list
except ImportError:  # pragma: no cover - supports running from scripts/
    from library_yaml import find_value, parse_entry_segments, parse_nested_list


ROOT = Path(__file__).resolve().parents[1]
LIBRARY_INDEX_PATH = Path("library_index.md")
CONTACTS_DIR = Path("content") / "profile" / "contacts"
SKILL_CATEGORIES_PATH = Path("content") / "taxonomy" / "skill_categories.yaml"
INDEX_FORMAT_VERSION = 2
INDEX_MARKER = re.compile(r"^<!-- index_format_version: (\d+); index_fingerprint: ([0-9a-f]{64}) -->$")


def display_value(value: str) -> str:
    return value if value else "None"


def write_list(handle: io.StringIO, values: list[str]) -> None:
    for value in values:
        handle.write(f"  - {value}\n")
    if not values:
        handle.write("  - None\n")


def parse_contact_profiles(root: Path) -> list[dict[str, str]]:
    profiles = []
    for path in sorted((root / CONTACTS_DIR).glob("*.yaml")):
        lines = path.read_text(encoding="utf-8").splitlines()
        profiles.append(
            {
                "path": path.relative_to(root).as_posix(),
                "profile_id": find_value(lines, "profile_id"),
                "profile_label": find_value(lines, "profile_label"),
                "full_name": find_value(lines, "full_name"),
                "email": find_value(lines, "email"),
                "phone": find_value(lines, "phone"),
                "linkedin_display": find_value(lines, "linkedin_display"),
                "location": find_value(lines, "location"),
                "language": find_value(lines, "language"),
                "target_market": find_value(lines, "target_market"),
            }
        )
    return profiles


def parse_skill_categories(root: Path) -> dict[str, dict[str, Any]]:
    path = root / SKILL_CATEGORIES_PATH
    if not path.exists():
        return {}
    lines = path.read_text(encoding="utf-8").splitlines()
    categories = {}
    for start, end in parse_entry_segments(lines, "category_id"):
        segment = lines[start:end]
        category_id = find_value(segment, "category_id")
        categories[category_id] = {
            "display_name": find_value(segment, "display_name"),
            "aliases": parse_nested_list(segment, "aliases"),
        }
    return categories


def compute_index_fingerprint(root: Path, catalog: dict[str, Any]) -> str:
    library_fingerprint = catalog.get("library_fingerprint")
    if not isinstance(library_fingerprint, str) or not re.fullmatch(r"[0-9a-f]{64}", library_fingerprint):
        raise ValueError("Compact catalog is missing a valid library_fingerprint.")

    digest = hashlib.sha256()
    digest.update(f"index-format:{INDEX_FORMAT_VERSION}\0".encode("ascii"))
    digest.update(library_fingerprint.encode("ascii"))
    for path in [root / SKILL_CATEGORIES_PATH, *sorted((root / CONTACTS_DIR).glob("*.yaml"))]:
        digest.update(b"\0")
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes() if path.exists() else b"<missing>")
    return digest.hexdigest()


def partition_candidate_pools(experience: dict[str, Any]) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    independent = []
    seen_pool_ids: set[str] = set()
    for pool in experience["candidate_bullet_pools"]:
        pool_id = str(pool["pool_id"])
        if pool_id in seen_pool_ids:
            raise ValueError(f"Duplicate pool ID in catalog experience {experience['experience_id']}: {pool_id}")
        seen_pool_ids.add(pool_id)
        group_id = pool.get("overlap_group_id")
        if group_id:
            grouped.setdefault(str(group_id), []).append(pool)
        else:
            independent.append(pool)
    return grouped, independent


def render_library_index(root: Path, catalog: dict[str, Any], index_fingerprint: str) -> str:
    education = catalog["education"]
    coursework = catalog["coursework"]
    skills = catalog["skills"]
    experiences = catalog["experiences"]
    contacts = parse_contact_profiles(root)
    categories = parse_skill_categories(root)
    candidate_sections = [partition_candidate_pools(experience) for experience in experiences]
    candidate_count = sum(len(experience["candidate_bullet_pools"]) for experience in experiences)

    handle = io.StringIO()
    handle.write("# Resume Library Index\n\n")
    handle.write(f"<!-- index_format_version: {INDEX_FORMAT_VERSION}; index_fingerprint: {index_fingerprint} -->\n\n")
    handle.write("This is the review view of the active library catalog. Canonical YAML remains the source of truth; contact profiles and skill-category labels are display-only additions.\n\n")
    handle.write("## Active Library Summary\n\n")
    handle.write(f"- Education entries: {len(education)}\n")
    handle.write(f"- Contact profiles: {len(contacts)}\n")
    handle.write(f"- Coursework entries: {len(coursework)}\n")
    handle.write(f"- Active skills: {len(skills)}\n")
    handle.write(f"- Skill categories: {len(categories)}\n")
    handle.write(f"- Canonical experiences: {len(experiences)}\n")
    handle.write(f"- Candidate bullet pools: {candidate_count}\n")
    handle.write("- Archive content is excluded from default resume generation.\n\n")

    handle.write("## Contact Profiles\n\n")
    for profile in contacts:
        handle.write(f"### {profile['profile_id']}\n\n")
        for label, field in (
            ("Label", "profile_label"),
            ("Language", "language"),
            ("Target market", "target_market"),
            ("Full name", "full_name"),
            ("Email", "email"),
            ("Phone", "phone"),
            ("LinkedIn display", "linkedin_display"),
            ("Location", "location"),
        ):
            handle.write(f"- {label}: {display_value(profile[field])}\n")
        handle.write(f"- Source file: `{profile['path']}`\n\n")
    if not contacts:
        handle.write("- No contact profiles found.\n\n")

    handle.write("## Education\n\n")
    for item in education:
        handle.write(f"### {item['institution_en']}\n\n")
        handle.write(f"- Education ID: `{item['education_id']}`\n")
        handle.write(f"- Degree: {item['degree_en']}\n")
        handle.write(f"- Location: {display_value(item['location'])}\n")
        handle.write(f"- Location display: {str(item['location_display']).lower()}\n")
        handle.write(f"- GPA display: {str(item['gpa_display']).lower()}\n")
        handle.write(f"- GPA: {display_value(item['gpa_en'])}\n")
        handle.write(f"- Date: {item['date']}\n")
        handle.write(f"- Status: {item['status']}\n\n")

    handle.write("## Coursework\n\n")
    for item in coursework:
        handle.write(f"### {item['title_en']}\n\n")
        handle.write(f"- Coursework ID: `{item['coursework_id']}`\n")
        handle.write(f"- Status: {item['status']}\n")
        handle.write(f"- Education IDs: {', '.join(item['education_ids']) if item['education_ids'] else 'None'}\n")
        handle.write(f"- Tools: {', '.join(item['tools']) if item['tools'] else 'None'}\n")
        handle.write("- Variants:\n")
        write_list(handle, item["variants"])
        handle.write("\n")

    handle.write("## Skills\n\n")
    skills_by_category: dict[str, list[dict[str, Any]]] = {}
    for skill in skills:
        skills_by_category.setdefault(skill["default_category"], []).append(skill)
    for category_id, category_skills in sorted(
        skills_by_category.items(),
        key=lambda item: categories.get(item[0], {}).get("display_name", item[0]),
    ):
        category = categories.get(category_id, {})
        handle.write(f"### {category.get('display_name', category_id)}\n\n")
        handle.write(f"- Category ID: `{category_id}`\n")
        handle.write(f"- Skills: {len(category_skills)}\n")
        handle.write(f"- Category aliases: {', '.join(category.get('aliases', [])) if category.get('aliases') else 'None'}\n\n")
        for skill in sorted(category_skills, key=lambda item: item["display_name"].lower()):
            aliases = [alias for alias in skill["aliases"] if alias != skill["display_name"]]
            handle.write(f"- **{skill['display_name']}** (`{skill['skill_id']}`)\n")
            handle.write(f"  - Status: {skill['status']}\n")
            handle.write(f"  - Aliases: {', '.join(aliases) if aliases else 'None'}\n")
        handle.write("\n")
    if not skills:
        handle.write("- No active skills found.\n\n")

    handle.write("## Canonical Experiences\n\n")
    for number, (experience, (grouped, independent)) in enumerate(zip(experiences, candidate_sections), start=1):
        canonical = experience["canonical"]
        sections = experience["display_section_rules"]
        handle.write(f"### {number}. {canonical['title_en']}\n\n")
        handle.write(f"- Experience ID: `{experience['experience_id']}`\n")
        handle.write(f"- Status: {experience['status']}\n")
        handle.write(f"- Organization: {canonical['organization_en']}\n")
        handle.write(f"- Location: {display_value(canonical['location'])}\n")
        handle.write(f"- Date: {canonical['date']}\n")
        handle.write(f"- Type: {canonical['experience_type']}\n")
        handle.write(f"- Default section: {sections['default_section']}\n")
        handle.write(f"- Allowed sections: {', '.join(sections['allowed_sections']) if sections['allowed_sections'] else 'None'}\n")
        for label, key in (("Role fit", "role_fit"), ("Tools", "tools"), ("Skills", "skills"), ("Keywords", "keywords")):
            handle.write(f"- {label}: {', '.join(experience[key]) if experience[key] else 'None'}\n")
        handle.write(f"- Candidate bullet pools: {len(experience['candidate_bullet_pools'])}\n")
        handle.write(f"- Overlap groups: {len(grouped)}\n")
        handle.write(f"- Grouped candidates: {sum(len(pools) for pools in grouped.values())}\n")
        handle.write(f"- Independent candidates: {len(independent)}\n")
        handle.write("- Title variants:\n")
        write_list(handle, experience["title_variants"])

        if grouped:
            handle.write("\n#### Grouped Candidates\n\n")
            for group_id, pools in sorted(grouped.items()):
                handle.write(f"##### {group_id}\n\n")
                for pool in pools:
                    handle.write(f"- `{pool['pool_id']}` {pool['text']}\n")
                handle.write("\n")
        if independent:
            handle.write("#### Independent Candidates\n\n")
            for pool in independent:
                handle.write(f"- `{pool['pool_id']}` {pool['text']}\n")
            handle.write("\n")

    return handle.getvalue().rstrip("\n") + "\n"


def refresh_library_index(root: Path, catalog: dict[str, Any]) -> bool:
    index_path = root / LIBRARY_INDEX_PATH
    fingerprint = compute_index_fingerprint(root, catalog)
    if index_path.exists():
        for line in index_path.read_text(encoding="utf-8").splitlines()[:4]:
            marker = INDEX_MARKER.fullmatch(line)
            if marker and int(marker.group(1)) == INDEX_FORMAT_VERSION and marker.group(2) == fingerprint:
                return False

    rendered = render_library_index(root, catalog, fingerprint)
    temporary_path = index_path.with_suffix(index_path.suffix + ".tmp")
    temporary_path.write_text(rendered, encoding="utf-8", newline="\n")
    temporary_path.replace(index_path)
    return True


def main() -> int:
    try:
        from scripts import phase6b_content_selection as phase6b
    except ImportError:  # pragma: no cover - supports running from scripts/
        import phase6b_content_selection as phase6b

    catalog_path = ROOT / phase6b.ACTIVE_LIBRARY_CATALOG_PATH
    catalog, catalog_regenerated = phase6b.ensure_compact_catalog(ROOT, catalog_path)
    index_regenerated = refresh_library_index(ROOT, catalog)
    print(f"Active library catalog {'regenerated' if catalog_regenerated else 'reused'}: {catalog_path}")
    print(f"Library index {'regenerated' if index_regenerated else 'reused'}: {ROOT / LIBRARY_INDEX_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
