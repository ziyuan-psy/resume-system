from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JD_INPUTS_DIRNAME = "jd_inputs"
ANALYSIS_DIR = Path("generated") / "analysis"
GENERATED_TEX_DIR = Path("generated") / "tex"
GENERATED_PDF_DIR = Path("generated") / "pdf"
SLUG_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9_-]{0,78}[a-z0-9])?$")

REQUIRED_ANALYSIS_MARKERS = [
    "# JD Analysis: {slug}",
    "Status: needs_review",
    "Source JD: jd_inputs/{slug}.txt",
    "Analysis method: Codex-assisted LLM review",
    "## Role Summary",
    "## Role Direction",
    "## Company / Product Context",
    "## Core Responsibilities",
    "## Required Qualifications",
    "## Preferred / Plus Qualifications",
    "## Skills And Tools Mentioned",
    "## Keywords And ATS Terms",
    "### Exact JD Terms To Preserve",
    "### Normalized Resume / ATS Phrases",
    "## Screening Criteria",
    "## Resume Emphasis For Phase 6B",
    "## Ambiguities Or Review Notes",
    "## Review Checklist",
]

ACCEPTED_SINGLE_TERM_KEYWORDS = {"AI", "SQL", "LLM", "RAG", "API"}


class Phase6AError(Exception):
    pass


@dataclass(frozen=True)
class SourceText:
    text: str
    source_type: str


@dataclass(frozen=True)
class Phase6APaths:
    jd_path: Path
    analysis_path: Path
    tex_path: Path
    pdf_path: Path


def normalize_storage_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if normalized and not normalized.endswith("\n"):
        normalized += "\n"
    return normalized


def validate_slug(slug: str) -> str:
    if not SLUG_PATTERN.fullmatch(slug):
        raise Phase6AError(
            "target_slug must use only lowercase letters, numbers, underscores, or hyphens; "
            "it cannot contain dots, spaces, slashes, or path traversal."
        )
    return slug


def ensure_path_under(root: Path, path: Path) -> None:
    root_resolved = root.resolve()
    path_resolved = path.resolve()
    try:
        path_resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise Phase6AError(f"Refusing to use a path outside project root: {path}") from exc


def build_paths(root: Path, slug: str) -> Phase6APaths:
    paths = Phase6APaths(
        jd_path=root / JD_INPUTS_DIRNAME / f"{slug}.txt",
        analysis_path=root / ANALYSIS_DIR / f"{slug}_jd_analysis.md",
        tex_path=root / GENERATED_TEX_DIR / f"{slug}.tex",
        pdf_path=root / GENERATED_PDF_DIR / f"{slug}.pdf",
    )
    for path in (paths.jd_path, paths.analysis_path, paths.tex_path, paths.pdf_path):
        ensure_path_under(root, path)
    return paths


def read_source_text(args: argparse.Namespace, jd_path: Path) -> SourceText | None:
    if args.use_existing:
        if not jd_path.exists():
            raise Phase6AError(f"Existing JD file not found: {jd_path}")
        return SourceText(jd_path.read_text(encoding="utf-8"), "existing_jd_file")

    if args.source_file:
        text = Path(args.source_file).read_text(encoding="utf-8")
        source_type = "confirmed_screenshot_transcription_file" if args.confirmed_screenshot_transcription else "source_file"
        return SourceText(text, source_type)

    if args.stdin:
        text = sys.stdin.read()
        source_type = "confirmed_screenshot_transcription_stdin" if args.confirmed_screenshot_transcription else "stdin"
        return SourceText(text, source_type)

    if args.text:
        source_type = "confirmed_screenshot_transcription_text" if args.confirmed_screenshot_transcription else "inline_text"
        return SourceText(args.text, source_type)

    return None


def write_jd_source(jd_path: Path, text: str, overwrite: bool) -> None:
    normalized = normalize_storage_text(text)
    if not normalized.strip():
        raise Phase6AError("JD text is empty after reading input.")

    if jd_path.exists():
        existing = normalize_storage_text(jd_path.read_text(encoding="utf-8"))
        if existing == normalized:
            return
        if not overwrite:
            raise Phase6AError(
                f"JD file already exists and differs: {jd_path}. "
                "Use --overwrite only after confirming the replacement text is faithful."
            )

    jd_path.parent.mkdir(parents=True, exist_ok=True)
    jd_path.write_text(normalized, encoding="utf-8", newline="\n")


def required_markers(slug: str) -> list[str]:
    return [marker.format(slug=slug) for marker in REQUIRED_ANALYSIS_MARKERS]


def validate_no_tex_or_pdf(paths: Phase6APaths) -> None:
    created_outputs = [path for path in (paths.tex_path, paths.pdf_path) if path.exists()]
    if created_outputs:
        formatted = ", ".join(str(path) for path in created_outputs)
        raise Phase6AError(f"Phase 6A must not create generated TeX or PDF outputs: {formatted}")


def extract_markdown_section(text: str, heading: str) -> list[str]:
    lines = text.splitlines()
    start = -1
    for index, line in enumerate(lines):
        if line.strip() == heading:
            start = index + 1
            break
    if start == -1:
        return []

    end = len(lines)
    for index in range(start, len(lines)):
        if lines[index].startswith("## "):
            end = index
            break
    return lines[start:end]


def keyword_word_count(value: str) -> int:
    return len(re.findall(r"[A-Za-z0-9]+(?:[-/][A-Za-z0-9]+)?", value))


def validate_keyword_bullets(analysis_text: str) -> None:
    keyword_lines = extract_markdown_section(analysis_text, "## Keywords And ATS Terms")
    errors = []

    for line in keyword_lines:
        stripped = line.strip()
        if not stripped.startswith("- "):
            continue

        value = stripped[2:].strip()
        if value.endswith((".", "?", "!")):
            errors.append(f"keyword bullet has trailing sentence punctuation: {value}")

        if keyword_word_count(value) < 2 and value not in ACCEPTED_SINGLE_TERM_KEYWORDS:
            errors.append(f"keyword bullet is too fragment-like: {value}")

    if errors:
        formatted = "\n".join(f"- {error}" for error in errors)
        raise Phase6AError(f"JD analysis has invalid keyword bullets:\n{formatted}")


def validate_analysis_file(paths: Phase6APaths, slug: str) -> None:
    if not paths.jd_path.exists():
        raise Phase6AError(f"JD source file does not exist: {paths.jd_path}")
    if not paths.analysis_path.exists():
        raise Phase6AError(f"JD analysis file does not exist yet: {paths.analysis_path}")

    analysis_text = paths.analysis_path.read_text(encoding="utf-8")
    missing = [marker for marker in required_markers(slug) if marker not in analysis_text]
    if missing:
        formatted = "\n".join(f"- {marker}" for marker in missing)
        raise Phase6AError(f"JD analysis is missing required contract markers:\n{formatted}")

    forbidden_phrases = [
        "deterministic scan",
        "score:",
        "evidence:",
        "source type:",
    ]
    lowered = analysis_text.lower()
    found_forbidden = [phrase for phrase in forbidden_phrases if phrase in lowered]
    if found_forbidden:
        formatted = ", ".join(found_forbidden)
        raise Phase6AError(f"JD analysis appears to contain obsolete deterministic-analysis language: {formatted}")

    validate_keyword_bullets(analysis_text)
    validate_no_tex_or_pdf(paths)


def render_analysis_contract(slug: str) -> str:
    return f"""Codex/LLM analysis contract for `{slug}`:

1. Read only `jd_inputs/{slug}.txt`.
2. Write `generated/analysis/{slug}_jd_analysis.md`.
3. Do not inspect active resume content, archive content, extracted CSVs, generated TeX, or generated PDFs.
4. Do not select resume content, generate LaTeX, or compile PDFs.
5. Use this exact Markdown section contract:

# JD Analysis: {slug}
Status: needs_review
Source JD: jd_inputs/{slug}.txt
Analysis method: Codex-assisted LLM review

## Role Summary
## Role Direction
## Company / Product Context
## Core Responsibilities
## Required Qualifications
## Preferred / Plus Qualifications
## Skills And Tools Mentioned
## Keywords And ATS Terms
### Exact JD Terms To Preserve
### Normalized Resume / ATS Phrases
## Screening Criteria
## Resume Emphasis For Phase 6B
## Ambiguities Or Review Notes
## Review Checklist

Analysis rules:
- Use the JD text only.
- Separate explicit JD requirements from inferred role signals.
- Do not invent qualifications or claim candidate fit.
- In `Keywords And ATS Terms`, separate exact JD phrases from normalized resume/ATS phrases.
- Keyword bullets must be concise noun phrases, not sentence fragments.
- Keyword bullets must not end with sentence punctuation.
- Do not include standalone generic words, pronouns, filler words, or isolated fragments.
- Reframe weak fragments into useful phrases, such as `conversation drop-off analysis`, `next-action guidance`, or `conversation flow optimization`.
- Make the analysis useful for later content selection, but do not select content in Phase 6A.
"""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Phase 6A JD intake and validation helper. Codex/LLM writes the analysis.",
    )
    parser.add_argument("--target-slug", required=True, help="Safe lowercase basename for JD and analysis outputs.")
    parser.add_argument("--root", default=str(ROOT), help=argparse.SUPPRESS)

    source_group = parser.add_mutually_exclusive_group()
    source_group.add_argument("--source-file", help="Read JD text from a local UTF-8 text file.")
    source_group.add_argument("--stdin", action="store_true", help="Read JD text from standard input.")
    source_group.add_argument("--text", help="Read JD text from an inline command argument.")
    source_group.add_argument("--use-existing", action="store_true", help="Use existing jd_inputs/<target_slug>.txt.")

    parser.add_argument(
        "--confirmed-screenshot-transcription",
        action="store_true",
        help="Document that source text came from a manually confirmed screenshot transcription.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing JD source after confirming the replacement text is faithful.",
    )
    parser.add_argument(
        "--validate-analysis",
        action="store_true",
        help="Validate that Codex has written the Phase 6A analysis contract and no TeX/PDF output exists.",
    )
    return parser.parse_args(argv)


def run(args: argparse.Namespace) -> Phase6APaths:
    root = Path(args.root).resolve()
    slug = validate_slug(args.target_slug)
    paths = build_paths(root, slug)
    source_text = read_source_text(args, paths.jd_path)

    if source_text is not None and not args.use_existing:
        write_jd_source(paths.jd_path, source_text.text, args.overwrite)
    elif not paths.jd_path.exists():
        raise Phase6AError(
            "No JD source was provided and jd_inputs/<target_slug>.txt does not exist. "
            "Use --source-file, --stdin, --text, or --use-existing."
        )

    if args.validate_analysis:
        validate_analysis_file(paths, slug)
    else:
        validate_no_tex_or_pdf(paths)

    return paths


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        slug = validate_slug(args.target_slug)
        paths = run(args)
    except Phase6AError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(f"JD source: {paths.jd_path}")
    print(f"Expected JD analysis: {paths.analysis_path}")
    print("Phase 6A helper complete. Python did not generate JD analysis text, TeX, or PDF.")
    if args.validate_analysis:
        print("Validated: analysis contract exists and no target TeX/PDF output exists.")
    else:
        print()
        print(render_analysis_contract(slug))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
