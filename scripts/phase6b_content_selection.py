from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from scripts import phase6a_jd_intake as phase6a
    from scripts.generate_library_index import (
        find_block,
        find_value,
        parse_entry_segments,
        parse_list_block,
        parse_nested_list,
    )
except ImportError:  # pragma: no cover - supports running from scripts/
    import phase6a_jd_intake as phase6a
    from generate_library_index import (
        find_block,
        find_value,
        parse_entry_segments,
        parse_list_block,
        parse_nested_list,
    )


ROOT = Path(__file__).resolve().parents[1]
SELECTION_DIR = Path("generated") / "selection"
CANONICAL_EN_DIR = Path("content") / "experiences" / "canonical" / "en"
EDUCATION_PATH = Path("content") / "profile" / "education.yaml"
COURSEWORK_PATH = Path("content") / "profile" / "coursework.yaml"
SKILLS_PATH = Path("content") / "profile" / "skills.yaml"
SELECTION_METHOD = "Codex-assisted hybrid bullet-first content matching"

PAGE_FIT_ESTIMATES = {"likely", "borderline", "too_long"}
ALLOWED_SECTION_TITLES = {"Professional Experience", "Project Experience", "Research Experience"}
NON_WORK_SECTION_TITLES = {"Project Experience", "Research Experience"}
SELECTION_TIERS = {"core", "supporting", "backup"}
FINAL_PRIORITIES = {"must_include", "include_if_space", "backup"}
SKILL_DISPLAY_PRIORITIES = {"core_jd", "supporting", "baseline_high_signal"}
TITLE_SOURCES = {"canonical", "title_variant"}
SOURCE_TYPES = {
    "work",
    "internship",
    "contractor_work",
    "applied_project",
    "research_project",
    "course_project",
    "coursework_only",
}
OVERLAP_RESOLUTIONS = {"kept", "combined", "preferred_overlapping_source"}
MATCH_TYPES = {"direct", "transferable_analogy"}
UNSUPPORTED_CLAIM_RISKS = {"low", "medium", "high"}
METRIC_PATTERN = re.compile(
    r"(?ix)"
    r"\bN\s*=\s*\d+(?:,\d{3})*\b"
    r"|"
    r"\b\d+(?:,\d{3})*(?:\.\d+)?\s*%"
    r"|"
    r"\b\d+(?:,\d{3})*(?:\.\d+)?\s*[kKmM]?\+?\s+"
    r"(?:[A-Za-z][A-Za-z/&+-]*(?:\s+[A-Za-z][A-Za-z/&+-]*){0,3})"
)
METRIC_CONTEXT_STOPWORDS = {
    "and",
    "or",
    "with",
    "for",
    "to",
    "in",
    "of",
    "on",
    "by",
    "from",
    "across",
    "through",
    "using",
    "via",
    "into",
}
METRIC_CONTEXT_BLOCKLIST = {
    "phase",
    "phases",
    "pool",
    "pools",
    "raw",
    "bullet",
    "bullets",
    "version",
    "versions",
    "schema",
    "schemas",
}


class Phase6BError(Exception):
    pass


@dataclass(frozen=True)
class SelectionPaths:
    jd_path: Path
    analysis_path: Path
    selection_path: Path
    selection_json_path: Path
    tex_path: Path
    pdf_path: Path


def ensure_path_under(root: Path, path: Path) -> None:
    root_resolved = root.resolve()
    path_resolved = path.resolve()
    try:
        path_resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise Phase6BError(f"Refusing to use a path outside project root: {path}") from exc


def build_paths(root: Path, slug: str) -> SelectionPaths:
    paths = SelectionPaths(
        jd_path=root / "jd_inputs" / f"{slug}.txt",
        analysis_path=root / "generated" / "analysis" / f"{slug}_jd_analysis.md",
        selection_path=root / SELECTION_DIR / f"{slug}_selection_plan.md",
        selection_json_path=root / SELECTION_DIR / f"{slug}_selection.json",
        tex_path=root / "generated" / "tex" / f"{slug}.tex",
        pdf_path=root / "generated" / "pdf" / f"{slug}.pdf",
    )
    for path in (
        paths.jd_path,
        paths.analysis_path,
        paths.selection_path,
        paths.selection_json_path,
        paths.tex_path,
        paths.pdf_path,
    ):
        ensure_path_under(root, path)
    return paths


def read_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


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
                "raw_bullet_ids": parse_nested_list(segment, "raw_bullet_ids"),
                "quality_flags": parse_nested_list(segment, "quality_flags"),
            }
        )
    return pools


def parse_bool_value(value: str, default: bool, field_name: str, context: str) -> bool:
    if not value:
        return default
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise Phase6BError(f"{field_name} in {context} must be true or false.")


def parse_education(root: Path) -> list[dict[str, object]]:
    path = root / EDUCATION_PATH
    if not path.exists():
        return []
    lines = read_lines(path)
    entries = []
    for start, end in parse_entry_segments(lines, "education_id"):
        segment = lines[start:end]
        education_id = find_value(segment, "education_id")
        context = f"education entry {education_id or 'unknown'}"
        gpa_en = find_value(segment, "gpa_en")
        gpa_display = parse_bool_value(find_value(segment, "gpa_display"), False, "gpa_display", context)
        location_display = parse_bool_value(find_value(segment, "location_display"), True, "location_display", context)
        if gpa_display and not gpa_en.strip():
            raise Phase6BError(f"{context} has gpa_display: true but missing gpa_en.")
        entries.append(
            {
                "education_id": education_id,
                "institution_en": find_value(segment, "institution_en"),
                "degree_en": find_value(segment, "degree_en"),
                "location": find_value(segment, "location"),
                "gpa_en": gpa_en,
                "gpa_display": gpa_display,
                "location_display": location_display,
                "date": find_value(segment, "date"),
                "status": find_value(segment, "status"),
            }
        )
    return entries


def parse_coursework(root: Path) -> list[dict[str, object]]:
    path = root / COURSEWORK_PATH
    if not path.exists():
        return []
    lines = read_lines(path)
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
            }
        )
    return entries


def parse_skills(root: Path) -> list[dict[str, object]]:
    path = root / SKILLS_PATH
    if not path.exists():
        return []
    lines = read_lines(path)
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
                "status": find_value(segment, "status"),
                "raw_skill_count": len(raw_skill_ids),
            }
        )
    return entries


def parse_canonical_experience(path: Path) -> dict[str, object]:
    lines = read_lines(path)
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
    }


def parse_canonical_experiences(root: Path) -> list[dict[str, object]]:
    directory = root / CANONICAL_EN_DIR
    if not directory.exists():
        return []
    return [parse_canonical_experience(path) for path in sorted(directory.glob("*.yaml"))]


def index_by(items: list[dict[str, object]], key: str) -> dict[str, dict[str, object]]:
    return {str(item[key]): item for item in items}


def pool_index_for_experience(experience: dict[str, object]) -> dict[str, dict[str, object]]:
    return {str(pool["pool_id"]): pool for pool in experience["candidate_bullet_pools"]}  # type: ignore[index]


def as_list(value: Any, field_name: str) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    raise Phase6BError(f"Selection JSON field must be a list: {field_name}")


def as_dict(value: Any, field_name: str) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    raise Phase6BError(f"Selection JSON field must be an object: {field_name}")


def required_text(item: dict[str, Any], field_name: str, context: str) -> str:
    value = item.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise Phase6BError(f"Missing required text field {field_name} in {context}.")
    return value.strip()


def required_bool(item: dict[str, Any], field_name: str, context: str) -> bool:
    value = item.get(field_name)
    if not isinstance(value, bool):
        raise Phase6BError(f"Missing required boolean field {field_name} in {context}.")
    return value


def required_number(item: dict[str, Any], field_name: str, context: str) -> int | float:
    value = item.get(field_name)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise Phase6BError(f"Missing required numeric field {field_name} in {context}.")
    return value


def required_enum(item: dict[str, Any], field_name: str, allowed: set[str], context: str) -> str:
    value = required_text(item, field_name, context)
    if value not in allowed:
        raise Phase6BError(f"{context} field {field_name} must be one of: {', '.join(sorted(allowed))}.")
    return value


def required_string_list(item: dict[str, Any], field_name: str, context: str) -> list[str]:
    values = as_list(item.get(field_name), f"{field_name} in {context}")
    result: list[str] = []
    for value in values:
        if not isinstance(value, str) or not value.strip():
            raise Phase6BError(f"{context} field {field_name} must contain only non-empty strings.")
        result.append(value.strip())
    return result


def normalize_metric_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace(",", "").strip().lower())


def metric_quantity_variants(quantity: str) -> set[str]:
    normalized = normalize_metric_text(quantity)
    variants = {normalized}
    match = re.fullmatch(r"(\d+(?:\.\d+)?)([km])(\+?)", normalized)
    if match:
        number = float(match.group(1))
        multiplier = 1000 if match.group(2) == "k" else 1000000
        expanded = int(number * multiplier)
        suffix = match.group(3)
        variants.add(f"{expanded}{suffix}")
        variants.add(f"{expanded:,}{suffix}".lower())
    expanded_match = re.fullmatch(r"(\d{4,})(\+?)", normalized)
    if expanded_match:
        number = int(expanded_match.group(1))
        suffix = expanded_match.group(2)
        if number % 1000 == 0 and number < 1000000:
            variants.add(f"{number // 1000}k{suffix}")
        if number % 1000000 == 0:
            variants.add(f"{number // 1000000}m{suffix}")
    return variants


def split_metric_quantity(metric: str) -> tuple[str, list[str]]:
    normalized = normalize_metric_text(metric)
    n_match = re.match(r"(n\s*=\s*\d+)(.*)", normalized)
    if n_match:
        return n_match.group(1).replace(" ", ""), re.findall(r"[a-z]+", n_match.group(2))
    match = re.match(r"(\d+(?:\.\d+)?(?:[km])?\+?|\d+(?:\.\d+)?%)(.*)", normalized)
    if not match:
        return normalized, []
    quantity = match.group(1)
    words = [word for word in re.findall(r"[a-z]+", match.group(2)) if word not in METRIC_CONTEXT_STOPWORDS]
    return quantity, words


def text_contains_metric(text: str, metric: str) -> bool:
    normalized_text = normalize_metric_text(text)
    normalized_metric = normalize_metric_text(metric)
    if normalized_metric in normalized_text:
        return True

    quantity, words = split_metric_quantity(metric)
    for variant in metric_quantity_variants(quantity):
        variant_normalized = normalize_metric_text(variant)
        position = normalized_text.find(variant_normalized)
        if position == -1:
            continue
        if not words:
            return True
        window = normalized_text[position : position + max(80, len(normalized_metric) + 40)]
        if all(re.search(rf"\b{re.escape(word)}\b", window) for word in words):
            return True
    return False


def equivalent_metric_in_list(metric: str, values: list[str]) -> bool:
    return any(text_contains_metric(value, metric) or text_contains_metric(metric, value) for value in values)


def trim_metric_candidate(candidate: str) -> str:
    candidate = re.sub(r"\s+", " ", candidate.strip(" .;:,()[]{}"))
    tokens = candidate.split()
    if not tokens:
        return ""
    trimmed = [tokens[0]]
    for token in tokens[1:]:
        clean_token = token.lower().strip(".,;:()[]{}")
        if clean_token in METRIC_CONTEXT_STOPWORDS:
            break
        trimmed.append(token)
    while trimmed and trimmed[-1].lower().strip(".,;:") in METRIC_CONTEXT_STOPWORDS:
        trimmed.pop()
    return " ".join(trimmed)


def is_high_signal_metric(candidate: str, source_text: str) -> bool:
    candidate = trim_metric_candidate(candidate)
    if not candidate:
        return False
    normalized = normalize_metric_text(candidate)
    prefix = source_text[max(0, source_text.lower().find(candidate.lower()) - 16) : source_text.lower().find(candidate.lower())].lower()
    if any(word in prefix.split()[-3:] for word in ("phase", "pool", "raw")):
        return False
    if re.fullmatch(r"(19|20)\d{2}", normalized):
        return False
    words = re.findall(r"[a-z]+", normalized)
    if words and words[0] in METRIC_CONTEXT_BLOCKLIST:
        return False
    if len(words) == 1 and words[0] in METRIC_CONTEXT_STOPWORDS:
        return False
    return True


def detect_source_metrics(source_text: str) -> list[str]:
    metrics: list[str] = []
    for match in METRIC_PATTERN.finditer(source_text):
        metric = trim_metric_candidate(match.group(0))
        if not is_high_signal_metric(metric, source_text):
            continue
        if not equivalent_metric_in_list(metric, metrics):
            metrics.append(metric)
    return metrics


def validate_quantitative_evidence(
    bullet: dict[str, Any],
    context: str,
    source_pool_ids: list[str],
    pool_details: list[dict[str, object]],
    overlap_resolution: str,
) -> None:
    requires_quantitative_evidence = len(source_pool_ids) > 1 or overlap_resolution == "combined"
    if not requires_quantitative_evidence:
        return

    evidence = as_dict(bullet.get("quantitative_evidence"), f"quantitative_evidence in {context}")
    source_metrics_detected = required_string_list(evidence, "source_metrics_detected", f"quantitative_evidence in {context}")
    metrics_preserved = required_string_list(evidence, "metrics_preserved", f"quantitative_evidence in {context}")
    metrics_omitted = required_string_list(evidence, "metrics_omitted", f"quantitative_evidence in {context}")
    omission_reason = evidence.get("omission_reason")
    if omission_reason is not None and (not isinstance(omission_reason, str) or not omission_reason.strip()):
        raise Phase6BError(f"quantitative_evidence in {context} omission_reason must be null or non-empty text.")
    if metrics_omitted and omission_reason is None:
        raise Phase6BError(f"quantitative_evidence in {context} must include omission_reason when metrics_omitted is not empty.")

    source_text = " ".join(str(pool["text"]) for pool in pool_details)
    actual_source_metrics = detect_source_metrics(source_text)
    draft_bullet_text = required_text(bullet, "draft_bullet_text", context)

    for metric in actual_source_metrics:
        if not equivalent_metric_in_list(metric, source_metrics_detected):
            raise Phase6BError(
                f"quantitative_evidence in {context} must list detected source metric: {metric}"
            )

    for metric in metrics_preserved:
        if not text_contains_metric(draft_bullet_text, metric):
            raise Phase6BError(
                f"quantitative_evidence in {context} lists preserved metric not found in draft_bullet_text: {metric}"
            )

    for metric in source_metrics_detected:
        metric_in_draft = text_contains_metric(draft_bullet_text, metric)
        if metric_in_draft and not equivalent_metric_in_list(metric, metrics_preserved):
            raise Phase6BError(
                f"quantitative_evidence in {context} must list preserved source metric: {metric}"
            )
        if not metric_in_draft and not equivalent_metric_in_list(metric, metrics_omitted):
            raise Phase6BError(
                f"quantitative_evidence in {context} must list omitted source metric or preserve it: {metric}"
            )

    for metric in actual_source_metrics:
        if not text_contains_metric(draft_bullet_text, metric) and not equivalent_metric_in_list(metric, metrics_omitted):
            raise Phase6BError(
                f"quantitative_evidence in {context} omitted detected source metric without omission record: {metric}"
            )


def validate_proposed_title_for_review(item: dict[str, Any], context: str) -> None:
    if "proposed_title_for_review" not in item:
        return
    proposed = item.get("proposed_title_for_review")
    if proposed is not None and (not isinstance(proposed, str) or not proposed.strip()):
        raise Phase6BError(f"{context} proposed_title_for_review must be null or non-empty text.")


def resolve_display_title(
    item: dict[str, Any],
    experience: dict[str, object],
    context: str,
    *,
    require_display_title: bool = True,
) -> str:
    validate_proposed_title_for_review(item, context)
    if "display_title" not in item or item.get("display_title") in (None, ""):
        if require_display_title:
            raise Phase6BError(f"Missing required text field display_title in {context}.")
        return str(experience["title_en"]).strip()

    display_title = required_text(item, "display_title", context)
    title_source = required_enum(item, "title_source", TITLE_SOURCES, context)
    required_text(item, "title_selection_rationale", context)

    canonical_title = str(experience["title_en"]).strip()
    title_variants = [str(title).strip() for title in experience.get("title_variants", []) if str(title).strip()]
    if display_title == canonical_title:
        expected_source = "canonical"
    elif display_title in title_variants:
        expected_source = "title_variant"
    else:
        raise Phase6BError(
            f"{context} display_title must match the canonical title or an existing title_variant: {display_title}"
        )

    if title_source != expected_source:
        raise Phase6BError(
            f"{context} title_source must be {expected_source} for display_title: {display_title}"
        )
    return display_title


def load_selection_json(root: Path, source: str) -> dict[str, Any]:
    if source == "-":
        raw_text = sys.stdin.read()
    else:
        path = Path(source)
        if not path.is_absolute():
            path = root / path
        ensure_path_under(root, path)
        raw_text = path.read_text(encoding="utf-8")

    if not raw_text.strip():
        raise Phase6BError("Selection JSON input is empty.")
    try:
        selection = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise Phase6BError(f"Selection JSON is not valid JSON: {exc}") from exc
    if not isinstance(selection, dict):
        raise Phase6BError("Selection JSON root must be an object.")
    return selection


def validate_resume_budget(selection: dict[str, Any]) -> None:
    budget = as_dict(selection.get("resume_budget"), "resume_budget")
    context = "resume_budget"
    required_number(budget, "target_pages", context)
    required_number(budget, "preferred_experience_blocks", context)
    required_number(budget, "maximum_experience_blocks", context)
    required_text(budget, "preferred_total_bullets", context)
    required_number(budget, "maximum_total_bullets", context)
    required_text(budget, "core_experience_bullets", context)
    required_text(budget, "supporting_experience_bullets", context)
    required_text(budget, "preferred_skill_category_lines", context)
    required_text(budget, "preferred_displayed_skills", context)
    required_text(budget, "preferred_coursework_count", context)
    required_enum(budget, "page_fit_estimate", PAGE_FIT_ESTIMATES, context)
    required_text(budget, "page_fit_note", context)


def validate_resume_section_plan(selection: dict[str, Any]) -> dict[str, Any]:
    section_plan = as_dict(selection.get("resume_section_plan"), "resume_section_plan")
    professional_title = required_text(section_plan, "professional_section_title", "resume_section_plan")
    if professional_title != "Professional Experience":
        raise Phase6BError('resume_section_plan professional_section_title must be "Professional Experience".')
    required_enum(section_plan, "non_work_section_title", NON_WORK_SECTION_TITLES, "resume_section_plan")
    required_text(section_plan, "section_rationale", "resume_section_plan")
    return section_plan


def validate_grounding_notes(bullet: dict[str, Any], context: str) -> None:
    notes = as_dict(bullet.get("grounding_notes"), f"grounding_notes in {context}")
    required_bool(notes, "new_facts_added", f"grounding_notes in {context}")
    required_bool(notes, "tools_or_metrics_changed", f"grounding_notes in {context}")
    required_enum(notes, "match_type", MATCH_TYPES, f"grounding_notes in {context}")
    required_enum(notes, "unsupported_claim_risk", UNSUPPORTED_CLAIM_RISKS, f"grounding_notes in {context}")
    required_text(notes, "note", f"grounding_notes in {context}")


def validate_skill_group(
    group: dict[str, Any],
    known_items: dict[str, dict[str, object]],
) -> None:
    selected_ids: set[str] = set()
    for item in as_list(group.get("selected_pool"), "skill_selections.selected_pool"):
        if not isinstance(item, dict):
            raise Phase6BError("Each skill_selections selected_pool item must be an object.")
        skill_id = required_text(item, "skill_id", "skill_selections selected_pool item")
        if skill_id not in known_items:
            raise Phase6BError(f"Unknown selected skill_id: {skill_id}")
        if skill_id in selected_ids:
            raise Phase6BError(f"Duplicate selected skill_id: {skill_id}")
        selected_ids.add(skill_id)
        required_text(item, "rationale", f"skill_selections selected_pool item {skill_id}")

    display_ids: set[str] = set()
    for item in as_list(group.get("recommended_final_display"), "skill_selections.recommended_final_display"):
        if not isinstance(item, dict):
            raise Phase6BError("Each skill_selections recommended_final_display item must be an object.")
        skill_id = required_text(item, "skill_id", "skill_selections recommended_final_display item")
        if skill_id not in known_items:
            raise Phase6BError(f"Unknown recommended skill_id: {skill_id}")
        if skill_id not in selected_ids:
            raise Phase6BError(f"Recommended skill_id must also appear in selected_pool: {skill_id}")
        if skill_id in display_ids:
            raise Phase6BError(f"Duplicate recommended skill_id: {skill_id}")
        display_ids.add(skill_id)
        required_text(item, "display_name", f"skill_selections recommended_final_display item {skill_id}")
        required_text(item, "display_category", f"skill_selections recommended_final_display item {skill_id}")
        required_enum(
            item,
            "display_priority",
            SKILL_DISPLAY_PRIORITIES,
            f"skill_selections recommended_final_display item {skill_id}",
        )
        required_text(item, "rationale", f"skill_selections recommended_final_display item {skill_id}")


def validate_coursework_group(
    group: dict[str, Any],
    id_field: str,
    known_items: dict[str, dict[str, object]],
    label: str,
) -> None:
    selected_ids: set[str] = set()
    for item in as_list(group.get("selected_pool"), f"{label}.selected_pool"):
        if not isinstance(item, dict):
            raise Phase6BError(f"Each {label} selected_pool item must be an object.")
        item_id = required_text(item, id_field, f"{label} selected_pool item")
        if item_id not in known_items:
            raise Phase6BError(f"Unknown selected {id_field}: {item_id}")
        if item_id in selected_ids:
            raise Phase6BError(f"Duplicate selected {id_field}: {item_id}")
        selected_ids.add(item_id)
        required_text(item, "rationale", f"{label} selected_pool item {item_id}")

    display_ids: set[str] = set()
    for item in as_list(group.get("recommended_final_display"), f"{label}.recommended_final_display"):
        if not isinstance(item, dict):
            raise Phase6BError(f"Each {label} recommended_final_display item must be an object.")
        item_id = required_text(item, id_field, f"{label} recommended_final_display item")
        if item_id not in known_items:
            raise Phase6BError(f"Unknown recommended {id_field}: {item_id}")
        if item_id not in selected_ids:
            raise Phase6BError(f"Recommended {id_field} must also appear in selected_pool: {item_id}")
        if item_id in display_ids:
            raise Phase6BError(f"Duplicate recommended {id_field}: {item_id}")
        display_ids.add(item_id)
        required_text(item, "rationale", f"{label} recommended_final_display item {item_id}")


def validate_trim_order(selection: dict[str, Any]) -> None:
    allowed_item_types = {"experience", "bullet", "skill", "coursework"}
    for index, item in enumerate(as_list(selection.get("trim_order"), "trim_order"), start=1):
        if not isinstance(item, dict):
            raise Phase6BError(f"trim_order item {index} must be an object.")
        required_enum(item, "item_type", allowed_item_types, f"trim_order item {index}")
        required_text(item, "id", f"trim_order item {index}")
        required_text(item, "reason", f"trim_order item {index}")


def validate_selection_json(
    selection: dict[str, Any],
    slug: str,
    experiences: dict[str, dict[str, object]],
    skills: dict[str, dict[str, object]],
    coursework: dict[str, dict[str, object]],
    *,
    require_display_titles: bool = True,
) -> None:
    if selection.get("target_slug") != slug:
        raise Phase6BError("Selection JSON target_slug does not match the requested target slug.")
    if selection.get("status") != "needs_review":
        raise Phase6BError('Selection JSON status must be "needs_review".')
    if selection.get("selection_method") != SELECTION_METHOD:
        raise Phase6BError(f'Selection JSON selection_method must be "{SELECTION_METHOD}".')

    required_text(selection, "role_direction", "selection root")
    required_text(selection, "selection_summary", "selection root")
    validate_resume_budget(selection)
    section_plan = validate_resume_section_plan(selection)
    non_work_section_title = str(section_plan["non_work_section_title"])

    seen_global_ranks: set[int] = set()
    seen_experiences = set()
    for item in as_list(selection.get("experience_selections"), "experience_selections"):
        if not isinstance(item, dict):
            raise Phase6BError("Each experience selection must be an object.")
        experience_id = required_text(item, "experience_id", "experience selection")
        if experience_id not in experiences:
            raise Phase6BError(f"Unknown selected experience_id: {experience_id}")
        if experience_id in seen_experiences:
            raise Phase6BError(f"Duplicate selected experience_id: {experience_id}")
        seen_experiences.add(experience_id)
        required_enum(item, "selection_tier", SELECTION_TIERS, f"experience selection {experience_id}")
        target_section = required_enum(item, "target_section", ALLOWED_SECTION_TITLES, f"experience selection {experience_id}")
        if target_section != "Professional Experience" and target_section != non_work_section_title:
            raise Phase6BError(
                f"experience selection {experience_id} target_section must match resume_section_plan non_work_section_title."
            )
        resolve_display_title(
            item,
            experiences[experience_id],
            f"experience selection {experience_id}",
            require_display_title=require_display_titles,
        )
        required_text(item, "rationale", f"experience selection {experience_id}")

        pools = pool_index_for_experience(experiences[experience_id])
        selected_bullets = as_list(item.get("selected_bullets"), f"selected_bullets for {experience_id}")
        if not 1 <= len(selected_bullets) <= 5:
            raise Phase6BError(f"Experience {experience_id} must have between 1 and 5 selected bullets.")

        seen_pool_ids: set[str] = set()
        for bullet_index, bullet in enumerate(selected_bullets, start=1):
            if not isinstance(bullet, dict):
                raise Phase6BError(f"Selected bullet {bullet_index} for {experience_id} must be an object.")
            context = f"selected bullet {bullet_index} for {experience_id}"
            source_pool_ids = [str(pool_id) for pool_id in as_list(bullet.get("source_pool_ids"), f"source_pool_ids in {context}")]
            if not source_pool_ids:
                raise Phase6BError(f"{context} must include at least one source_pool_id.")
            if len(source_pool_ids) != len(set(source_pool_ids)):
                raise Phase6BError(f"{context} repeats a source_pool_id within the same rendered bullet.")
            repeated = sorted(pool_id for pool_id in source_pool_ids if pool_id in seen_pool_ids)
            if repeated:
                raise Phase6BError(
                    f"{context} reuses source_pool_ids already used by another rendered bullet: {', '.join(repeated)}"
                )
            for pool_id in source_pool_ids:
                if pool_id not in pools:
                    raise Phase6BError(f"Unknown source_pool_id for {experience_id}: {pool_id}")
                seen_pool_ids.add(pool_id)

            global_rank = bullet.get("global_rank")
            if not isinstance(global_rank, int) or global_rank < 1:
                raise Phase6BError(f"{context} must include a positive integer global_rank.")
            if global_rank in seen_global_ranks:
                raise Phase6BError(f"Duplicate global_rank in selected bullets: {global_rank}")
            seen_global_ranks.add(global_rank)
            required_enum(bullet, "final_resume_priority", FINAL_PRIORITIES, context)
            required_enum(bullet, "source_type", SOURCE_TYPES, context)
            required_number(bullet, "jd_fit_score", context)
            required_number(bullet, "evidence_strength_score", context)
            required_number(bullet, "source_context_weight", context)
            required_number(bullet, "final_selection_score", context)
            required_text(bullet, "score_rationale", context)
            required_text(bullet, "draft_bullet_text", context)
            required_text(bullet, "source_fit_reason", context)
            overlap_resolution = required_enum(bullet, "overlap_resolution", OVERLAP_RESOLUTIONS, context)
            validate_grounding_notes(bullet, context)
            if len(source_pool_ids) > 1 and overlap_resolution != "combined":
                raise Phase6BError(f"{context} must use overlap_resolution combined when multiple source pools are used.")
            if len(source_pool_ids) == 1 and overlap_resolution == "combined":
                raise Phase6BError(f"{context} uses combined but has only one source pool.")
            validate_quantitative_evidence(
                bullet,
                context,
                source_pool_ids,
                [pools[pool_id] for pool_id in source_pool_ids],
                overlap_resolution,
            )

    validate_skill_group(as_dict(selection.get("skill_selections"), "skill_selections"), skills)
    validate_coursework_group(
        as_dict(selection.get("coursework_selections"), "coursework_selections"),
        "coursework_id",
        coursework,
        "coursework_selections",
    )
    validate_trim_order(selection)
    as_list(selection.get("review_notes"), "review_notes")


def list_text(values: list[str]) -> str:
    return ", ".join(values) if values else "None"


def item_rationale(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("rationale", "")).strip() or "Selected by Codex based on the Phase 6A JD analysis."
    return "Selected by Codex based on the Phase 6A JD analysis."


def selected_pool_details(
    selected_bullet: dict[str, Any],
    pools: dict[str, dict[str, object]],
) -> tuple[list[str], list[dict[str, object]]]:
    source_pool_ids = [str(pool_id) for pool_id in selected_bullet["source_pool_ids"]]
    pool_details = [pools[pool_id] for pool_id in source_pool_ids]
    return source_pool_ids, pool_details


def write_selection_json(path: Path, selection: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(selection, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def normalize_title_review_fields(selection: dict[str, Any]) -> None:
    for item in as_list(selection.get("experience_selections"), "experience_selections"):
        if isinstance(item, dict):
            item.setdefault("proposed_title_for_review", None)


def build_education_display_rules(education: list[dict[str, object]], page_fit_estimate: str) -> dict[str, object]:
    page_fit_is_tight = page_fit_estimate in {"borderline", "too_long"}
    notes_by_id = {
        "ut_austin_msis": "Include by default. Education is not ranked like experiences or bullets.",
        "nanjing_normal_applied_psychology": "Include by default. Education is not ranked like experiences or bullets.",
        "lingnan_exchange": (
            "Page budget is tight, so Lingnan University is the first education entry that can be dropped."
            if page_fit_is_tight
            else "Include by default only in compact form. Lingnan University is the first education entry to drop if page fit becomes tight."
        ),
    }
    entries = []
    for item in education:
        education_id = str(item["education_id"])
        if education_id == "lingnan_exchange":
            display_mode = "drop_if_tight" if page_fit_is_tight else "compact"
            include_by_default = not page_fit_is_tight
            drop_priority = 1
        else:
            display_mode = "standard"
            include_by_default = True
            drop_priority = None
        entries.append(
            {
                "education_id": education_id,
                "include_by_default": include_by_default,
                "display_mode": display_mode,
                "drop_priority": drop_priority,
                "note": notes_by_id.get(education_id, "Education display rule needs review."),
            }
        )
    return {
        "rule_method": "Fixed education display rule; education is not ranked like experiences or bullets.",
        "page_fit_is_tight": page_fit_is_tight,
        "entries": entries,
    }


def write_resume_budget(handle: Any, budget: dict[str, Any]) -> None:
    handle.write("## Resume Budget\n\n")
    handle.write(f"- Target pages: {budget['target_pages']}\n")
    handle.write(f"- Preferred experience blocks: {budget['preferred_experience_blocks']}\n")
    handle.write(f"- Maximum experience blocks: {budget['maximum_experience_blocks']}\n")
    handle.write(f"- Preferred total bullets: {budget['preferred_total_bullets']}\n")
    handle.write(f"- Maximum total bullets: {budget['maximum_total_bullets']}\n")
    handle.write(f"- Core experience bullets: {budget['core_experience_bullets']}\n")
    handle.write(f"- Supporting experience bullets: {budget['supporting_experience_bullets']}\n")
    handle.write(f"- Preferred skill category lines: {budget['preferred_skill_category_lines']}\n")
    handle.write(f"- Preferred displayed skills: {budget['preferred_displayed_skills']}\n")
    handle.write(f"- Preferred coursework count: {budget['preferred_coursework_count']}\n")
    handle.write(f"- Page-fit estimate: {budget['page_fit_estimate']}\n")
    handle.write(f"- Page-fit note: {budget['page_fit_note']}\n\n")


def write_selection_plan(
    root: Path,
    paths: SelectionPaths,
    slug: str,
    selection: dict[str, Any],
    education: list[dict[str, object]],
    experiences: dict[str, dict[str, object]],
    skills: dict[str, dict[str, object]],
    coursework: dict[str, dict[str, object]],
) -> None:
    paths.selection_path.parent.mkdir(parents=True, exist_ok=True)
    with paths.selection_path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(f"# Content Selection Plan: {slug}\n\n")
        handle.write(f"Generated: {datetime.now().astimezone().replace(microsecond=0).isoformat()}\n")
        handle.write("Status: needs_review\n")
        handle.write(f"Source JD: `jd_inputs/{slug}.txt`\n")
        handle.write(f"Source analysis: `generated/analysis/{slug}_jd_analysis.md`\n")
        handle.write(f"Selection JSON: `generated/selection/{slug}_selection.json`\n")
        handle.write(f"Selection method: {SELECTION_METHOD}; Python validated IDs and rendered Codex-provided selection JSON.\n\n")

        handle.write("## Guardrails\n\n")
        handle.write("- Phase 6B produces content selection artifacts only.\n")
        handle.write("- No LaTeX or PDF output is generated.\n")
        handle.write("- Archive content and raw extraction CSVs are not active sources.\n")
        handle.write("- Codex ranks candidate bullets globally before grouping selected bullets by experience.\n")
        handle.write("- Python validates active IDs and renders Markdown/JSON; it does not rank content.\n")
        handle.write("- Draft bullets remain review-needed and must stay grounded in the listed source pools.\n\n")

        handle.write("## Active Sources Used\n\n")
        handle.write("- `content/profile/education.yaml`\n")
        handle.write("- `content/profile/coursework.yaml`\n")
        handle.write("- `content/profile/skills.yaml`\n")
        handle.write("- `content/experiences/canonical/en/*.yaml`\n\n")

        experience_selections = as_list(selection.get("experience_selections"), "experience_selections")
        skill_selections = as_dict(selection.get("skill_selections"), "skill_selections")
        coursework_selections = as_dict(selection.get("coursework_selections"), "coursework_selections")
        selected_skill_pool = as_list(skill_selections.get("selected_pool"), "skill_selections.selected_pool")
        final_skill_display = as_list(skill_selections.get("recommended_final_display"), "skill_selections.recommended_final_display")
        selected_coursework_pool = as_list(coursework_selections.get("selected_pool"), "coursework_selections.selected_pool")
        final_coursework_display = as_list(
            coursework_selections.get("recommended_final_display"),
            "coursework_selections.recommended_final_display",
        )
        bullet_count = sum(
            len(as_list(item.get("selected_bullets"), "selected_bullets")) for item in experience_selections if isinstance(item, dict)
        )

        handle.write("## Selection Summary\n\n")
        handle.write(f"- Role direction: {selection['role_direction']}\n")
        handle.write(f"- Selection summary: {selection['selection_summary']}\n")
        section_plan = as_dict(selection["resume_section_plan"], "resume_section_plan")
        handle.write(f"- Professional section title: {section_plan['professional_section_title']}\n")
        handle.write(f"- Non-work section title: {section_plan['non_work_section_title']}\n")
        handle.write("- Education rule: UT Austin and Nanjing Normal University are included by default; Lingnan University is compact by default and first to drop when page fit is tight.\n")
        handle.write(f"- Experiences selected by Codex: {len(experience_selections)}\n")
        handle.write(f"- Rendered bullets selected: {bullet_count}\n")
        handle.write(f"- Skills selected pool: {len(selected_skill_pool)}\n")
        handle.write(f"- Recommended final skills display: {len(final_skill_display)}\n")
        handle.write(f"- Coursework selected pool: {len(selected_coursework_pool)}\n")
        handle.write(f"- Recommended final coursework display: {len(final_coursework_display)}\n\n")

        write_resume_budget(handle, as_dict(selection["resume_budget"], "resume_budget"))

        handle.write("## Resume Section Plan\n\n")
        handle.write(f"- Professional section title: {section_plan['professional_section_title']}\n")
        handle.write(f"- Non-work section title: {section_plan['non_work_section_title']}\n")
        handle.write(f"- Section rationale: {section_plan['section_rationale']}\n\n")

        education_rules = as_dict(selection["education_display_rules"], "education_display_rules")
        rules_by_id = {str(item["education_id"]): item for item in as_list(education_rules.get("entries"), "education_display_rules.entries") if isinstance(item, dict)}

        handle.write("## Education Display Rule\n\n")
        handle.write(f"{education_rules['rule_method']}\n\n")
        handle.write(f"- Page fit is tight: {str(education_rules['page_fit_is_tight']).lower()}\n")
        handle.write("- UT Austin: include by default.\n")
        handle.write("- Nanjing Normal University: include by default.\n")
        handle.write("- Lingnan University: include by default only in compact form unless page budget is tight; if tight, drop Lingnan first.\n\n")
        for item in education:
            rule = rules_by_id.get(str(item["education_id"]), {})
            handle.write(f"- `{item['education_id']}` {item['degree_en']}, {item['institution_en']}\n")
            handle.write(f"  - Date: {item['date']}\n")
            handle.write(f"  - Location: {item['location']}\n")
            if item.get("gpa_display"):
                handle.write(f"  - GPA: {item['gpa_en']}\n")
            handle.write(f"  - Location display: {str(item.get('location_display', True)).lower()}\n")
            handle.write(f"  - Status: {item['status']}\n")
            handle.write(f"  - Include by default: {str(rule.get('include_by_default', False)).lower()}\n")
            handle.write(f"  - Display mode: {rule.get('display_mode', 'needs_review')}\n")
            if rule.get("drop_priority") is not None:
                handle.write(f"  - Drop priority: {rule['drop_priority']}\n")
            handle.write(f"  - Note: {rule.get('note', 'needs_review')}\n")
        handle.write("\n")

        handle.write("## Selected Experiences\n\n")
        for index, selection_item in enumerate(experience_selections, start=1):
            experience_id = str(selection_item["experience_id"])
            exp = experiences[experience_id]
            display_title = resolve_display_title(selection_item, exp, f"experience selection {experience_id}")
            proposed_title = selection_item.get("proposed_title_for_review")
            handle.write(f"### {index}. {display_title} - {exp['organization_en']}\n\n")
            handle.write(f"- Experience ID: `{experience_id}`\n")
            handle.write(f"- Display title: {display_title}\n")
            handle.write(f"- Title source: {selection_item['title_source']}\n")
            handle.write(f"- Title selection rationale: {selection_item['title_selection_rationale']}\n")
            handle.write(
                "- Proposed title for review: "
                f"{proposed_title if proposed_title else 'None'}"
                " (review-only; not rendered by default)\n"
            )
            handle.write(f"- Selection tier: {selection_item['selection_tier']}\n")
            handle.write(f"- Target section: {selection_item['target_section']}\n")
            handle.write(f"- Source file: `{exp['path'].relative_to(root).as_posix()}`\n")
            handle.write(f"- Status: {exp['status']}\n")
            handle.write(f"- Type: {exp['experience_type']}\n")
            handle.write(f"- Date: {exp['date']}\n")
            handle.write(f"- Codex rationale: {item_rationale(selection_item)}\n")
            notes = as_list(selection_item.get("notes"), f"notes for {experience_id}")
            if notes:
                handle.write("- Notes:\n")
                for note in notes:
                    handle.write(f"  - {note}\n")
            handle.write("- Selected bullets:\n")
            pools = pool_index_for_experience(exp)
            selected_bullets = sorted(
                as_list(selection_item.get("selected_bullets"), f"selected_bullets for {experience_id}"),
                key=lambda bullet: int(bullet["global_rank"]),
            )
            for bullet in selected_bullets:
                source_pool_ids, pool_details = selected_pool_details(bullet, pools)
                grounding = as_dict(bullet["grounding_notes"], "grounding_notes")
                handle.write(f"  - Global rank: {bullet['global_rank']}\n")
                handle.write(f"    - Final resume priority: {bullet['final_resume_priority']}\n")
                handle.write(f"    - Source pool IDs: {list_text(source_pool_ids)}\n")
                handle.write("    - Source candidate text:\n")
                for pool in pool_details:
                    handle.write(f"      - `{pool['pool_id']}` {pool['text']}\n")
                handle.write(f"    - Draft bullet text: {bullet['draft_bullet_text']}\n")
                handle.write(f"    - Fit reason: {bullet['source_fit_reason']}\n")
                handle.write(
                    "    - Score summary: "
                    f"JD fit {bullet['jd_fit_score']}; "
                    f"evidence {bullet['evidence_strength_score']}; "
                    f"context weight {bullet['source_context_weight']}; "
                    f"final {bullet['final_selection_score']}\n"
                )
                handle.write(f"    - Score rationale: {bullet['score_rationale']}\n")
                handle.write(f"    - Source type: {bullet['source_type']}\n")
                handle.write(f"    - Overlap resolution: {bullet['overlap_resolution']}\n")
                handle.write(
                    "    - Grounding note: "
                    f"new facts added = {str(grounding['new_facts_added']).lower()}; "
                    f"tools or metrics changed = {str(grounding['tools_or_metrics_changed']).lower()}; "
                    f"match type = {grounding['match_type']}; "
                    f"unsupported claim risk = {grounding['unsupported_claim_risk']}; "
                    f"{grounding['note']}\n"
                )
                if len(source_pool_ids) > 1 or bullet["overlap_resolution"] == "combined":
                    quantitative = as_dict(bullet.get("quantitative_evidence"), "quantitative_evidence")
                    omission_reason = quantitative.get("omission_reason")
                    handle.write(
                        "    - Quantitative evidence: "
                        f"detected = {list_text([str(item) for item in as_list(quantitative.get('source_metrics_detected'), 'source_metrics_detected')])}; "
                        f"preserved = {list_text([str(item) for item in as_list(quantitative.get('metrics_preserved'), 'metrics_preserved')])}; "
                        f"omitted = {list_text([str(item) for item in as_list(quantitative.get('metrics_omitted'), 'metrics_omitted')])}; "
                        f"omission reason = {omission_reason if omission_reason else 'None'}\n"
                    )
            handle.write("\n")

        handle.write("## Skills Selected Pool\n\n")
        handle.write("Selected pool is the broader candidate/backup pool; not every selected skill must appear in the final resume.\n\n")
        for item in selected_skill_pool:
            skill_id = str(item["skill_id"])
            skill = skills[skill_id]
            handle.write(f"- `{skill_id}` {skill['display_name']}\n")
            handle.write(f"  - Status: {skill['status']}\n")
            handle.write(f"  - Default category: {skill['default_category']}\n")
            handle.write(f"  - Rationale: {item_rationale(item)}\n")
            handle.write(f"  - Raw skill rows: {skill['raw_skill_count']}\n")
        handle.write("\n")

        handle.write("## Recommended Final Skills Display\n\n")
        handle.write("Recommended final display is the actual skill set intended for the LaTeX Skills section. Display categories are authored by Codex/LLM for this resume and are not mechanically assigned from `skills.yaml`.\n\n")
        for item in final_skill_display:
            skill_id = str(item["skill_id"])
            handle.write(f"- `{skill_id}` {item['display_name']}\n")
            handle.write(f"  - Display category: {item['display_category']}\n")
            handle.write(f"  - Display priority: {item['display_priority']}\n")
            handle.write(f"  - Rationale: {item_rationale(item)}\n")
        handle.write("\n")

        handle.write("## Coursework Selected Pool\n\n")
        for item in selected_coursework_pool:
            coursework_id = str(item["coursework_id"])
            course = coursework[coursework_id]
            handle.write(f"- `{coursework_id}` {course['title_en']}\n")
            handle.write(f"  - Status: {course['status']}\n")
            handle.write(f"  - Education IDs: {list_text(course['education_ids'])}\n")
            handle.write(f"  - Tools: {list_text(course['tools'])}\n")
            handle.write(f"  - Rationale: {item_rationale(item)}\n")
        handle.write("\n")

        handle.write("## Recommended Final Coursework Display\n\n")
        for item in final_coursework_display:
            coursework_id = str(item["coursework_id"])
            course = coursework[coursework_id]
            handle.write(f"- `{coursework_id}` {course['title_en']}\n")
            handle.write(f"  - Rationale: {item_rationale(item)}\n")
        handle.write("\n")

        handle.write("## Trim Order\n\n")
        for item in as_list(selection.get("trim_order"), "trim_order"):
            handle.write(f"- `{item['item_type']}` `{item['id']}`: {item['reason']}\n")
        handle.write("\n")

        handle.write("## Codex Review Notes\n\n")
        review_notes = as_list(selection.get("review_notes"), "review_notes")
        if review_notes:
            for note in review_notes:
                handle.write(f"- {note}\n")
        else:
            handle.write("- None.\n")
        handle.write("\n")

        handle.write("## Review Checklist\n\n")
        handle.write("- [ ] Selected experiences are relevant to the JD analysis.\n")
        handle.write("- [ ] Every rendered bullet has source pool IDs and source candidate text.\n")
        handle.write("- [ ] Combined bullets are faithful to all listed source candidate texts.\n")
        handle.write("- [ ] Draft bullets do not add unsupported facts, tools, metrics, or responsibilities.\n")
        handle.write("- [ ] Skills and coursework final display choices fit the resume budget.\n")
        handle.write("- [ ] This plan is ready for Phase 6C LaTeX draft generation.\n")


def validate_selection_outputs(paths: SelectionPaths) -> None:
    if not paths.selection_path.exists():
        raise Phase6BError(f"Selection plan was not created: {paths.selection_path}")
    if not paths.selection_json_path.exists():
        raise Phase6BError(f"Selection JSON was not created: {paths.selection_json_path}")

    text = paths.selection_path.read_text(encoding="utf-8")
    required_markers = [
        "# Content Selection Plan:",
        "Status: needs_review",
        f"Selection method: {SELECTION_METHOD}",
        "Selection JSON:",
        "## Resume Section Plan",
        "Professional section title:",
        "Non-work section title:",
        "Display title:",
        "Title source:",
        "Title selection rationale:",
        "## Resume Budget",
        "Page-fit estimate:",
        "## Education Display Rule",
        "Lingnan University: include by default only in compact form",
        "## Selected Experiences",
        "Selection tier:",
        "Target section:",
        "Source pool IDs:",
        "Source candidate text:",
        "Draft bullet text:",
        "Score summary:",
        "Overlap resolution:",
        "Grounding note:",
        "## Skills Selected Pool",
        "## Recommended Final Skills Display",
        "Display category:",
        "Display priority:",
        "## Coursework Selected Pool",
        "## Recommended Final Coursework Display",
        "## Trim Order",
        "## Review Checklist",
    ]
    missing = [marker for marker in required_markers if marker not in text]
    if missing:
        raise Phase6BError("Selection plan is missing required markers: " + ", ".join(missing))

    forbidden = [
        "Selection manifest",
        "Duplicate count",
        "Source reference count",
        "Raw bullet count",
        "Raw bullet IDs",
        "Traceability Appendix",
        "content/archive",
        "extracted/raw_",
        "raw_overleaf_exports",
        "generated/tex",
        "generated/pdf",
    ]
    found = [value for value in forbidden if value in text]
    if found:
        raise Phase6BError("Selection plan references forbidden content or old fields: " + ", ".join(found))
    selection = json.loads(paths.selection_json_path.read_text(encoding="utf-8"))
    if selection.get("selection_method") != SELECTION_METHOD:
        raise Phase6BError("Selection JSON artifact has the wrong selection_method.")
    if "resume_section_plan" not in selection:
        raise Phase6BError("Selection JSON artifact is missing resume_section_plan.")
    if "education_display_rules" not in selection:
        raise Phase6BError("Selection JSON artifact is missing education_display_rules.")


def render_selection_contract(slug: str) -> str:
    return f"""Codex/LLM Phase 6B selection JSON contract for `{slug}`:

1. Read only these inputs:
   - `jd_inputs/{slug}.txt`
   - `generated/analysis/{slug}_jd_analysis.md`
   - `content/profile/education.yaml`
   - `content/profile/coursework.yaml`
   - `content/profile/skills.yaml`
   - `content/experiences/canonical/en/*.yaml`
2. Do not inspect archive content, raw extraction CSVs, generated TeX, or generated PDFs.
3. Rank candidate bullet pools globally against the Phase 6A JD analysis before grouping by experience.
4. Author resume_section_plan and each experience target_section using only the supported template section titles.
5. Author each experience display_title using only the canonical title or existing title_variants from active YAML.
6. Put any invented title idea only in proposed_title_for_review; it will not render by default.
7. Author display_category and display_priority for each recommended final skill.
8. Resolve overlapping bullets under the same experience by keeping the stronger source pool or combining source pools.
9. For combined/multi-source bullets, preserve high-signal quantitative evidence in draft_bullet_text whenever possible and include quantitative_evidence metadata.
10. Pipe selected JSON to Python with `--selection-json -`.
11. Python writes `generated/selection/{slug}_selection_plan.md` and `generated/selection/{slug}_selection.json`.
12. Use the schema documented in README Phase 6B.
"""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 6B renderer for Codex-selected active content.")
    parser.add_argument("--target-slug", required=True, help="Safe lowercase basename used for JD, analysis, and selection files.")
    parser.add_argument("--selection-json", help='Codex-authored selection JSON path, or "-" to read from stdin.')
    parser.add_argument("--validate-only", action="store_true", help="Validate existing selection Markdown and JSON outputs without rendering.")
    parser.add_argument("--root", default=str(ROOT), help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def run(args: argparse.Namespace) -> SelectionPaths:
    root = Path(args.root).resolve()
    slug = phase6a.validate_slug(args.target_slug)
    paths = build_paths(root, slug)
    phase6a.validate_analysis_file(
        phase6a.Phase6APaths(
            jd_path=paths.jd_path,
            analysis_path=paths.analysis_path,
            tex_path=paths.tex_path,
            pdf_path=paths.pdf_path,
        ),
        slug,
        validate_no_generated_outputs=False,
    )

    if args.validate_only:
        validate_selection_outputs(paths)
        return paths

    if not args.selection_json:
        return paths

    selection = load_selection_json(root, args.selection_json)
    education = parse_education(root)
    experiences_by_id = index_by(parse_canonical_experiences(root), "experience_id")
    skills_by_id = index_by(parse_skills(root), "skill_id")
    coursework_by_id = index_by(parse_coursework(root), "coursework_id")
    validate_selection_json(selection, slug, experiences_by_id, skills_by_id, coursework_by_id)
    selection_output = copy.deepcopy(selection)
    normalize_title_review_fields(selection_output)
    budget = as_dict(selection_output["resume_budget"], "resume_budget")
    selection_output["education_display_rules"] = build_education_display_rules(education, str(budget["page_fit_estimate"]))
    write_selection_json(paths.selection_json_path, selection_output)
    write_selection_plan(root, paths, slug, selection_output, education, experiences_by_id, skills_by_id, coursework_by_id)
    validate_selection_outputs(paths)
    return paths


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        paths = run(args)
    except (phase6a.Phase6AError, Phase6BError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.validate_only:
        print(f"Selection plan validated: {paths.selection_path}")
        print(f"Selection JSON validated: {paths.selection_json_path}")
    elif args.selection_json:
        print(f"Selection plan: {paths.selection_path}")
        print(f"Selection JSON: {paths.selection_json_path}")
        print("Phase 6B complete. Python validated and rendered Codex-provided selection JSON; no TeX or PDF was produced.")
    else:
        print("Selection JSON was not provided. Python did not select content or generate selection outputs.")
        print()
        print(render_selection_contract(phase6a.validate_slug(args.target_slug)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
