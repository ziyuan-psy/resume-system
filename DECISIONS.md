# Decisions

## Phase 1.5 Content Curation

- Raw extracted content is immutable. `extracted/raw_bullets.csv` and `extracted/raw_experiences.csv` are traceability data and must not be rewritten during curation.
- Education is managed separately from experience content in `content/profile/education.yaml`.
- Coursework is dynamic profile metadata in `content/profile/coursework.yaml`, not part of fixed education entries.
- Skills are profile-level content in `content/profile/skills.yaml`, not part of a specific experience.
- Contact/header information is profile-level content in `content/profile/contacts/`.
- Skill categories are managed in `content/taxonomy/skill_categories.yaml` and are display metadata, not skill identity.
- Interests detected in historical skills sections are excluded from active skills and default resume generation.
- Extracurricular content is archived by default.
- Usability Testing of Online PDF Tools is excluded from active content.
- Section is display logic, not an identity attribute for canonical experiences.
- Canonical experiences preserve historical title variants in `title_variants`.
- Archive content must be excluded from default resume generation.
- Canonical bullets must come from extracted content or user-approved content only.
- Skills are selected from display names, aliases, categories, and source evidence; v1 does not infer role tags or skill types.
- Phase 6C is deterministic LaTeX rendering only. It must not select, rank, rewrite, re-categorize, generate PDFs, or depend on PDFs.
- English Phase 6C supports only `us_en` and `china_intl_en` contact profiles. `china_domestic_zh` is reserved for a future Chinese resume workflow. Contact profile is selected during rendering, not Phase 6B content selection.
- JD-aware experience display titles must come from active YAML canonical titles or `title_variants`; new title ideas stay in `proposed_title_for_review` until explicitly approved.

## When to update this file

`DECISIONS.md` is not a changelog. It should only be updated when a change affects long-term architecture, data model, workflow rules, or generation rules.

Changes that should update `DECISIONS.md`:

- Changing the canonical experience schema.
- Changing active generation source folders.
- Changing education, coursework, archive, or generated resume management rules.
- Changing Codex rewrite/generation permissions.
- Changing status workflow such as `needs_review` / `approved` / `excluded`.
- Changing Chinese resume localization strategy.

Changes that do not need to update `DECISIONS.md`:

- Fixing typos.
- Updating one title, date, or organization.
- Regenerating `library_index.md`.
- Routine content cleanup.
- Reviewing or approving individual bullets.
- Updating source references.
