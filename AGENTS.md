# AGENTS.md

This file is the repo-level operating guide for Codex and other AI agents working in this `resume-system` repository. `README.md` is the human-facing project overview; `DECISIONS.md` records long-term architecture and workflow decisions.

## Project Purpose

This repo is a structured resume system that turns historical LaTeX resume materials into a reusable content library and generates JD-tailored LaTeX resume drafts from verified existing content.

This repo is building toward English and Chinese resume generation, but the current implemented workflow focuses on English resume content and English LaTeX draft generation.

AI agents may select, organize, lightly adapt, and render from verified content. Agents must not freely invent resume content.

## Source Of Truth

Active generation sources:

- `content/profile/education.yaml`
- `content/profile/coursework.yaml`
- `content/profile/skills.yaml`
- `content/profile/contacts/`
- `content/taxonomy/skill_categories.yaml`
- `content/experiences/canonical/en/*.yaml`
- `templates/us_resume_template.tex`
- `jd_inputs/<target_slug>.txt` as local JD input only

Excluded or non-active sources by default:

- `content/archive/**`
- `extracted/raw_*.csv`
- `raw_overleaf_exports/**`
- `extracted/tex_files/**`
- `generated/pdf/**`
- existing `generated/tex/**` except the specific output target

Raw extracted files are traceability data, not active generation sources. Archive content must not be used for default resume generation. PDFs are outputs, not source data. Do not use generated PDFs or historical PDFs as source content for Phase 6.

## Generated Artifacts

- `generated/**` and `jd_inputs/**` are local ignored artifacts.
- Do not force-add ignored generated artifacts or JD inputs unless the user explicitly asks.
- Do not commit generated TeX, PDF, JD, analysis, or selection artifacts by default.
- PDF generation is manual through VS Code and `pdflatex` unless explicitly requested.
- Phase 6C must not create, modify, overwrite, or depend on PDFs.
- If a PDF already exists from manual preview, leave it untouched.

## Phase 6 Boundaries

Phase 6A:

- Saves or reuses JD input.
- Codex/LLM writes JD analysis Markdown.
- Python validates the analysis contract.
- Do not inspect resume content during Phase 6A.
- Do not select resume content.
- Do not generate TeX or PDF.

Phase 6B:

- Codex/LLM performs content-selection judgment, including JD fit, global bullet ranking, overlap handling, display title selection, section placement, skill display category planning, and rationale writing.
- Python freshness-checks `generated/selection_inputs/active_library_catalog.json` on every run, regenerating it only when active source content or catalog schema changes.
- Python also freshness-checks `library_index.md`, the human-readable catalog view, and rewrites it only when the catalog, contact profiles, category labels, or index format changes.
- Codex should use the compact catalog for Phase 6B selection; canonical YAML remains the source of truth and the compact catalog remains an ignored derived artifact.
- Python validates IDs, the current library fingerprint, schema, grounding fields, quantitative evidence, and renders selection JSON and Markdown.
- Canonical overlap groups are enforced: separate rendered bullets may not use different members of the same group; group members may coexist only in one combined rendered bullet.
- Do not generate TeX or PDF.
- Experience `display_title` must come from the canonical title or existing `title_variants`.
- `proposed_title_for_review` is review-only and must not be rendered.
- Combined or multi-source bullets must preserve high-signal quantitative evidence or explain omissions.

Phase 6C:

- Deterministically renders LaTeX from validated Phase 6B selection JSON.
- Uses active content YAML, selected contact profile, and template anchors.
- Does not select, rank, rewrite, re-categorize, or generate PDFs.
- Leaves existing PDFs untouched.
- Supports English LaTeX resume drafts only in the current implementation.

## English And Chinese Workflow Scope

Current supported workflow:

- English source library
- English JD analysis
- English Phase 6 selection
- English LaTeX draft generation
- English contact profiles such as `us_en` and `china_intl_en`

Future or reserved workflow:

- Chinese domestic resume generation
- Chinese localization
- Chinese resume templates
- `china_domestic_zh` rendering

Do not create Chinese workflow files unless explicitly requested. Do not modify Chinese-resume assumptions unless the task is specifically about a Chinese resume phase. Do not claim Chinese generation is currently implemented.

## Content Integrity Rules

- Do not invent employers, schools, titles, dates, tools, metrics, responsibilities, outcomes, or project scope.
- Bullet adaptation must stay grounded in selected source pools.
- Quantitative metrics should be preserved when combining bullets unless omission is explicitly explained.
- New experience titles should go only into `proposed_title_for_review` until approved and added to active YAML.
- Skills are profile-level content.
- Skill categories are display metadata, not skill identity.
- Section placement is display logic, not experience identity.

## Git Rules

- Do not commit or push unless explicitly asked.
- Do not use `git add .` by default.
- Stage only task-relevant files.
- Before committing, show `git diff --stat`, `git status --short`, and `git diff --cached --stat` after staging.
- Keep commits small and logically scoped.
- Do not force-add ignored artifacts unless explicitly instructed.

## Validation And Reporting

For code changes:

- Run relevant Python compile checks.
- Run relevant tests if tests exist.
- Show validation commands and summaries.

For Phase 6 work:

- Stop immediately if any validation fails.
- Show the failing command and error.
- Do not continue to the next phase after a failed validation.

For documentation-only changes:

- Show `git diff --stat`.
- Show `git status --short`.
- Summarize the documentation change.

## Relationship With Other Docs

- `README.md` is the human-facing project overview and usage guide.
- `DECISIONS.md` records long-term architecture and workflow decisions and is not a changelog.
- `AGENTS.md` is the AI-agent operating guide for this repo.
- The local `resume-jd-generation` Codex skill is a user-level workflow trigger; `AGENTS.md` is repo-level behavior guidance.
