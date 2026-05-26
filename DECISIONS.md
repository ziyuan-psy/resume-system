# Decisions

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
