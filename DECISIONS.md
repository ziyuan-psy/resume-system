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
