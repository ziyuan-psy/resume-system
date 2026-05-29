# Resume System

## 1\. Project Goal

This project builds a structured, AI-assisted resume workflow that can generate tailored English and Chinese resumes from a reusable resume content library.

The system will convert historical Overleaf LaTeX resume projects into a structured content database. Later, when a new job description is provided, the system should select the most relevant experiences and bullet points, assemble them into a LaTeX template, and generate a polished PDF resume.

The goal is **not** to let AI freely write resumes from scratch. The goal is to let AI select, organize, lightly adapt, and generate resumes based on verified existing content.

\---

## 2\. Current Situation

The user currently has:

* 70+ Overleaf resume projects.
* Each project contains LaTeX source files.
* 300+ exported PDF resumes stored locally.
* Some PDFs have different filenames but identical or highly similar content.
* Around 70+ actually distinct resume versions.
* All current resume materials are written in English.
* The user needs both English and Chinese resumes for US and China job applications.

Historically, the user edited resumes in Overleaf, previewed the rendered PDF, exported the PDF, and saved it locally.

Now the goal is to migrate from scattered Overleaf projects and PDF files into a reusable structured resume library.

\---

## 3\. Key Design Decision

The new source of truth should be:

```text
A local + GitHub private repository containing structured resume content.
```

Overleaf should no longer be the center of the workflow. It can remain as a backup or optional final visual check, but the main workflow should happen in:

```text
VS Code + GitHub private repo + local LaTeX compilation + Codex/Python scripts
```

PDFs are outputs, not source data.

\---

## 4\. Important Principles

Follow these principles throughout the project:

1. **Do not invent content.**

   * Do not create fake metrics, responsibilities, tools, employers, schools, or project outcomes.
   * Only use information extracted from the user's historical resumes or explicitly added by the user.
2. **Preserve traceability.**

   * Each extracted bullet should keep a reference to its source project and source `.tex` file.
   * Do not permanently delete raw extracted content.
3. **Separate raw content from cleaned content.**

   * Raw extracted files should remain available.
   * Cleaned, deduplicated, and structured content should be saved separately.
4. **Use English as the initial source library.**

   * The current historical resume materials are in English.
   * Chinese resume content can be added later as localized versions, not literal one-time translations.
5. **Keep the MVP simple.**

   * The first version should focus on importing, extracting, deduplicating, and indexing.
   * Do not build a web app or a fully automated resume generator in the first phase.

\---

## 5\. Target Folder Structure

Recommended full project structure:

```text
resume-system/
  raw\_overleaf\_exports/
    overleaf\_bulk\_export\_2026-05-25/
      project\_001.zip
      project\_002.zip
      project\_003.zip

  extracted/
    tex\_files/
    raw\_bullets.csv
    raw\_experiences.csv
    deduplicated\_bullets.csv
    duplicate\_report.md
    extraction\_log.md

  content/
    experiences/
      en/
        ut\_career\_ai\_agent.yaml
        loreal\_sensory\_lab.yaml
        thrive\_product\_project.yaml
      zh/
        ut\_career\_ai\_agent.yaml
        loreal\_sensory\_lab.yaml

    bullets/
      bullet\_bank\_en.yaml
      bullet\_bank\_zh.yaml

    tags/
      role\_tags.yaml
      skill\_tags.yaml
      industry\_tags.yaml

  templates/
    us\_resume\_template.tex
    cn\_resume\_template.tex

  jd\_inputs/
    sample\_product\_ops\_jd.txt
    sample\_ai\_ops\_jd.txt

  generated/
    tex/
    pdf/

  scripts/
    unzip\_overleaf\_exports.py
    extract\_from\_tex.py
    deduplicate\_bullets.py
    generate\_library\_index.py
    generate\_resume.py
    compile\_pdf.py

  library\_index.md
  README.md
  AGENTS.md
```

For the MVP, a simpler structure is acceptable:

```text
resume-system/
  raw\_overleaf\_exports/
  extracted/
    raw\_bullets.csv
    deduplicated\_bullets.csv
    extraction\_log.md
    duplicate\_report.md
  content/
    experiences/
      en/
  scripts/
    unzip\_overleaf\_exports.py
    extract\_from\_tex.py
    deduplicate\_bullets.py
    generate\_library\_index.py
  library\_index.md
  README.md
```

\---

## 6\. Data Model

The content library should have two levels of classification.

### 6.1 Experience / Project Level

Each experience or project should have metadata describing where it fits.

Example:

```yaml
experience\_id: ut\_career\_ai\_agent
title\_en: AI-Powered Career Systems Graduate Assistant
title\_zh: AI 驱动职业系统研究生助理
organization\_en: UT Austin Career Success
organization\_zh: 德克萨斯大学奥斯汀分校 Career Success
location: Austin, TX
date: 2025 - Present
section\_type: work\_experience

role\_fit:
  - ai\_operations
  - product\_operations
  - knowledge\_management
  - workflow\_automation

tools:
  - SharePoint
  - Copilot Studio
  - Microsoft Teams
  - Power Automate
  - Excel
```

This level answers:

```text
Which types of roles is this experience suitable for?
```

\---

### 6.2 Bullet Level

Each bullet should have its own tags, because different bullets under the same experience may fit different roles.

Example:

```yaml
bullets:
  - bullet\_id: ut\_ai\_agent\_b01
    text\_en: "Built a structured tester feedback and change-log workflow to translate coach feedback into prioritized AI agent improvements."
    text\_zh: "搭建测试反馈与更新日志机制，将职业教练的使用反馈转化为可优先级排序的 AI Agent 优化项。"
    tags:
      role:
        - ai\_operations
        - product\_operations
        - program\_management
      skills:
        - feedback\_loop
        - stakeholder\_communication
        - workflow\_design
        - change\_management
      keywords:
        - AI implementation
        - feedback management
        - change log
        - stakeholder alignment
    source\_references:
      - source\_project: example\_overleaf\_project
        source\_tex\_file: main.tex
```

This level answers:

```text
Which specific bullets should be selected for a specific job description?
```

\---

## 7\. English and Chinese Resume Strategy

English content should be treated as the initial source material.

Chinese content should not be generated through literal translation every time. Instead, each important English bullet should eventually have a localized Chinese version.

Recommended approach:

```text
Stage 1: Build and clean the English resume library first.
Stage 2: Add Chinese versions for high-priority experiences and bullets.
Stage 3: Optimize Chinese bullets for China job applications and HR screening style.
```

Each bullet can share the same `bullet\_id`, but have both `text\_en` and `text\_zh`.

This allows English and Chinese resumes to use the same underlying verified facts while having different language styles.

\---

## 8\. Full Project Workflow

### Phase 0: Manual Preparation by User

The user will manually do:

```text
1. Create a local folder named resume-system.
2. Bulk download all Overleaf project source files.
3. Put all downloaded project zip files into raw\_overleaf\_exports/.
```

The user does not need to manually open or clean all `.tex` files.

\---

### Phase 1: Import Historical LaTeX Resumes

Codex should:

```text
1. Unzip all files under raw\_overleaf\_exports/.
2. Preserve original project names and paths.
3. Find all .tex files.
4. Copy or index all discovered .tex files under extracted/tex\_files/.
5. Create extraction\_log.md documenting:
   - number of zip files found
   - number of projects extracted
   - number of .tex files found
   - files that could not be parsed
```

Important rule:

```text
Do not rewrite resume content in this phase.
Only extract and organize.
```

\---

### Phase 2: Extract Resume Content

Codex should parse the LaTeX files and extract:

```text
- Section names
- Experience titles
- Organizations
- Dates
- Locations
- Bullet points
- Source project name
- Source tex file path
```

Output files:

```text
extracted/raw\_bullets.csv
extracted/raw\_experiences.csv
```

Suggested columns for `raw\_bullets.csv`:

```text
source\_project
source\_tex\_file
section\_name
experience\_title
organization
date
bullet\_text
detected\_tools
possible\_role\_tags
```

\---

### Phase 3: Deduplicate Content

Codex should identify:

```text
- Exact duplicate bullets
- Near-duplicate bullets
- Same experience with different bullet versions
- Same PDF/source with different filenames if applicable
```

For deduplication, Codex may normalize bullet text by:

```text
- Removing extra spaces
- Removing LaTeX syntax where possible
- Normalizing punctuation
- Lowercasing for comparison
```

Output:

```text
extracted/deduplicated\_bullets.csv
extracted/duplicate\_report.md
```

Important rule:

```text
Do not delete source content permanently.
Keep raw extracted content and create cleaned versions separately.
```

\---

### Phase 4: Build Initial Resume Content Library

Codex should convert cleaned content into structured YAML files.

Each experience should become one YAML file under:

```text
content/experiences/en/
```

For the first version, only English content is required.

Each file should include:

```text
experience\_id
title\_en
organization\_en
location
date
section\_type
role\_fit
tools
bullets
```

Each bullet should include:

```text
bullet\_id
text\_en
text\_zh
tags
source\_references
```

For the MVP, `text\_zh` can be empty.

\---

### Phase 5: Generate Human-Readable Library Index

Codex should generate a Markdown file:

```text
library\_index.md
```

This file should allow the user to visually review the content library.

It should show:

```text
- All experiences/projects
- Their role-fit tags
- Tools and skills
- All bullet versions
- Source references
- Suggested role categories
```

This is the file the user will mainly review.

\---

### Phase 6: Resume Generation from JD

After the library is built, the user can paste a job description into:

```text
jd\_inputs/
```

Codex should then:

```text
1. Read the JD.
2. Identify role direction, required skills, preferred skills, keywords, and screening criteria.
3. Search the resume content library.
4. Select the most relevant experiences.
5. Select the strongest bullets under each experience.
6. Assemble a LaTeX resume using the correct template.
7. Output a .tex file under generated/tex/.
8. Compile the .tex file into PDF under generated/pdf/.
```

Important rule:

```text
Codex should prioritize verified existing content.
Codex should not invent work experience, metrics, tools, or responsibilities.
```

#### Phase 6A: JD Intake and Analysis

Phase 6A stores a reproducible job description source and creates a reviewable Codex-assisted JD analysis. The Python helper handles file I/O and validation only; Codex/LLM reads the saved JD and writes the analysis. Phase 6A does not select resume content, generate LaTeX, or compile PDFs.

Step 1: save or reuse the JD source.

```text
python scripts/phase6a_jd_intake.py --target-slug sample_product_ops --source-file path/to/job_description.txt
python scripts/phase6a_jd_intake.py --target-slug sample_product_ops --use-existing
```

Step 2: ask Codex to read only:

```text
jd_inputs/<target_slug>.txt
```

and write:

```text
generated/analysis/<target_slug>_jd_analysis.md
```

using this section contract:

```text
# JD Analysis: <target_slug>
Status: needs_review
Source JD: jd_inputs/<target_slug>.txt
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
```

Step 3: validate the analysis.

```text
python scripts/phase6a_jd_intake.py --target-slug sample_product_ops --validate-analysis
```

The analysis is marked `needs_review` and should separate explicit JD requirements from inferred role signals. `Keywords And ATS Terms` should use concise noun phrases with no trailing sentence punctuation. Exact JD terms should preserve meaningful phrases from the posting, while normalized resume/ATS phrases may reframe real JD concepts for later matching without inventing new requirements. For example, `where users drop off` should become `conversation drop-off analysis` or stay under responsibilities, and `right next action` should become `next-action guidance` or `conversation flow optimization`. Codex should not inspect resume content, archive content, raw extracted CSVs, generated TeX, or generated PDFs during Phase 6A.

#### Phase 6B: Content Selection Plan

Phase 6B uses Codex/LLM judgment for hybrid bullet-first content matching, ranking, overlap resolution, and final display recommendation. Python does not rank content in this phase; it validates Codex-selected active IDs, writes a normalized machine-readable selection JSON artifact, and renders a human-readable Markdown plan. Phase 6B does not generate LaTeX, compile PDFs, or use archive/raw extraction sources as active inputs. Education is not ranked or selected like experiences or bullets. UT Austin and Nanjing Normal University are included by default. Lingnan University is included by default only in compact form unless page budget is tight; if page fit is tight, Lingnan University is the first education entry that can be dropped.

Step 1: ask Codex to read only:

```text
jd_inputs/<target_slug>.txt
generated/analysis/<target_slug>_jd_analysis.md
content/profile/education.yaml
content/profile/coursework.yaml
content/profile/skills.yaml
content/experiences/canonical/en/*.yaml
```

Codex should:

```text
1. Rank candidate bullet pools globally against the Phase 6A JD analysis.
2. Choose bullets based on JD fit before favoring experience structure or source type.
3. Remove or combine overlapping bullets under the same experience.
4. Group selected bullets by experience afterward.
5. Order experiences by grouped strength, relevance, coherence, and resume narrative.
6. Produce a selected pool and recommended final display set for skills and coursework.
```

Source context should influence ranking, but it must not dominate JD relevance. A direct project or research match can outrank a weakly relevant work bullet. Suggested context weights: work `1.00`, internship/GA/contractor `0.95-1.00`, applied product or technical project `0.85-0.95`, research project `0.80-0.90`, course project `0.75-0.85`, and coursework-only evidence `0.50-0.70`.

Step 2: pipe Codex-authored selection JSON into the renderer.

```text
python scripts/phase6b_content_selection.py --target-slug sample_product_ops --selection-json -
```

Selection JSON shape:

```json
{
  "target_slug": "<target_slug>",
  "status": "needs_review",
  "selection_method": "Codex-assisted hybrid bullet-first content matching",
  "role_direction": "short role direction",
  "selection_summary": "one-sentence summary of the selection strategy",
  "resume_budget": {
    "target_pages": 1,
    "preferred_experience_blocks": 4,
    "maximum_experience_blocks": 5,
    "preferred_total_bullets": "10-13",
    "maximum_total_bullets": 14,
    "core_experience_bullets": "3-4",
    "supporting_experience_bullets": "1-2",
    "preferred_skill_category_lines": "2-3",
    "preferred_displayed_skills": "10-14",
    "preferred_coursework_count": "3-5",
    "page_fit_estimate": "likely | borderline | too_long",
    "page_fit_note": "Phase 6B only estimates page fit. Exact fit must be checked after Phase 6C LaTeX rendering in VS Code."
  },
  "experience_selections": [
    {
      "experience_id": "active_experience_id",
      "selection_tier": "core | supporting | backup",
      "rationale": "why this grouped experience belongs",
      "selected_bullets": [
        {
          "source_pool_ids": ["pool_id_1"],
          "global_rank": 1,
          "final_resume_priority": "must_include | include_if_space | backup",
          "source_type": "work | internship | contractor_work | applied_project | research_project | course_project | coursework_only",
          "jd_fit_score": 0,
          "evidence_strength_score": 0,
          "source_context_weight": 1.0,
          "final_selection_score": 0,
          "score_rationale": "why this score is appropriate",
          "draft_bullet_text": "JD-tuned bullet text grounded in the source pools",
          "source_fit_reason": "why this bullet fits",
          "overlap_resolution": "kept | combined | preferred_overlapping_source",
          "grounding_notes": {
            "new_facts_added": false,
            "tools_or_metrics_changed": false,
            "match_type": "direct | transferable_analogy",
            "unsupported_claim_risk": "low | medium | high",
            "note": "grounding note"
          }
        }
      ],
      "notes": []
    }
  ],
  "skill_selections": {
    "selected_pool": [
      {
        "skill_id": "active_skill_id",
        "rationale": "why this skill fits the JD"
      }
    ],
    "recommended_final_display": [
      {
        "skill_id": "active_skill_id",
        "rationale": "why this skill should appear in the compact resume"
      }
    ]
  },
  "coursework_selections": {
    "selected_pool": [
      {
        "coursework_id": "active_coursework_id",
        "rationale": "why this coursework fits the JD"
      }
    ],
    "recommended_final_display": [
      {
        "coursework_id": "active_coursework_id",
        "rationale": "why this coursework should appear in the compact resume"
      }
    ]
  },
  "trim_order": [
    {
      "item_type": "experience | bullet | skill | coursework",
      "id": "item_id_or_pool_id",
      "reason": "Remove this first if rendered resume is too long."
    }
  ],
  "review_notes": []
}
```

Selection rules:

```text
Each selected experience must have 1-5 rendered bullets.
source_pool_ids may contain multiple pool IDs only when overlapping source bullets are combined.
draft_bullet_text may be JD-tuned in Phase 6B, but must remain grounded in the listed source pools.
Python validates every experience_id, skill_id, coursework_id, and source_pool_id against active YAML.
Python rejects duplicate source_pool_ids under the same experience unless they are combined into the same rendered bullet.
Skills should include a broader selected pool and a smaller recommended final display set.
Coursework should include a broader selected pool and 3-5 recommended final display entries when possible.
```

Output:

```text
generated/selection/<target_slug>_selection_plan.md
generated/selection/<target_slug>_selection.json
```

Active sources:

```text
content/profile/education.yaml
content/profile/coursework.yaml
content/profile/skills.yaml
content/experiences/canonical/en/*.yaml
```

The Markdown selection plan is for human review. The JSON selection artifact is for Phase 6C LaTeX rendering, which should render the recommended final display set rather than blindly rendering every selected pool item. Generated selection artifacts are ignored local outputs and should not be force-added unless explicitly requested.

Python adds `education_display_rules` to the normalized selection JSON artifact. This is a deterministic display rule, not an education ranking: UT Austin and Nanjing Normal University remain default entries, while Lingnan University is compact by default and becomes the first education drop when `page_fit_estimate` is `borderline` or `too_long`.

The selection plan must preserve review traceability by listing selected `experience_id`, source candidate pool IDs, source candidate text, draft bullet text, fit rationale, score summary, overlap resolution, and grounding note. The plan should not include raw bullet IDs, raw bullet counts, duplicate counts, source reference counts, archive/raw paths as active sources, generated TeX/PDF output paths, or legacy intermediate artifact paths. All Phase 6B output is marked `needs_review` and should be checked before Phase 6C.

\---

## 9\. MVP Plan

### 9.1 MVP Goal

Build a working first version that can:

```text
1. Import historical Overleaf LaTeX files.
2. Extract resume bullets.
3. Deduplicate exact duplicates.
4. Generate a reviewable content index.
5. Create a simple structured English resume library.
```

The MVP does **not** need to fully automate perfect resume generation yet.

\---

### 9.2 MVP Scope

User manually does:

```text
1. Create resume-system folder.
2. Download Overleaf project source zip files.
3. Place zip files into raw\_overleaf\_exports/.
```

Codex does:

```text
1. Unzip all Overleaf project files.
2. Find all .tex files.
3. Extract bullet points and surrounding experience information.
4. Generate raw\_bullets.csv.
5. Deduplicate exact duplicate bullets.
6. Generate library\_index.md.
7. Create initial YAML files for the most frequently appearing experiences.
```

\---

### 9.3 MVP Deliverables

Codex should produce:

```text
1. extracted/extraction\_log.md
2. extracted/raw\_bullets.csv
3. extracted/deduplicated\_bullets.csv
4. extracted/duplicate\_report.md
5. content/experiences/en/\*.yaml
6. library\_index.md
```

\---

### 9.4 MVP Success Criteria

The MVP is successful if:

```text
- All Overleaf source files are successfully imported.
- Most resume bullets are extracted correctly.
- Exact duplicate bullets are identified.
- The user can open library\_index.md and clearly see all major experiences and bullet versions.
- The user can manually review, edit, and approve the extracted content.
```

The MVP does **not** need to:

```text
- Generate a perfect resume automatically.
- Translate all content into Chinese.
- Build a web interface.
- Fully classify every bullet.
- Sync back to Overleaf.
```

\---

## 10\. First Codex Task Prompt

Use the following prompt for the first Codex task:

```text
I am building a resume content library from my historical Overleaf resume projects.

Project context:
- I have 90+ Overleaf resume projects exported as source zip files.
- These files are stored under raw\_overleaf\_exports/.
- The final goal is to build a structured resume content library that can generate tailored English and Chinese LaTeX resumes.
- For this first phase, do not rewrite or invent any resume content. Only extract, organize, and deduplicate.

Please complete the MVP:

1. Create the project folder structure:
   - extracted/
   - content/experiences/en/
   - scripts/

2. Unzip all files under raw\_overleaf\_exports/.
   Preserve source project names and paths.

3. Find all .tex files.

4. Extract resume content from the .tex files:
   - section names
   - experience titles
   - organizations if detectable
   - dates if detectable
   - bullet points
   - source project name
   - source tex file path

5. Create extracted/raw\_bullets.csv with columns:
   - source\_project
   - source\_tex\_file
   - section\_name
   - experience\_title
   - organization
   - date
   - bullet\_text
   - detected\_tools
   - possible\_role\_tags

6. Deduplicate exact duplicate bullet points after normalizing spaces, LaTeX syntax, and punctuation.
   Create:
   - extracted/deduplicated\_bullets.csv
   - extracted/duplicate\_report.md

7. Generate library\_index.md so I can review the extracted resume library in a human-readable format.

8. Create initial YAML files under content/experiences/en/ for the most frequent or most clearly detected experiences.

Rules:
- Do not invent content.
- Do not permanently delete raw extracted content.
- Preserve source references for every bullet.
- Keep the first version simple and reviewable.
- The priority is extraction quality and traceability, not perfect resume generation yet.
```

\---

## 11\. Recommended Next Step

Before running Codex, the user should create this folder:

```text
resume-system/
  raw\_overleaf\_exports/
```

Then place all downloaded Overleaf source zip files into:

```text
resume-system/raw\_overleaf\_exports/
```

After that, open the `resume-system` folder in Codex/VS Code and run the first Codex task prompt above.



---

## Project Decisions

For long-term architecture and workflow decisions, see `DECISIONS.md`. `DECISIONS.md` is not a changelog and should only be updated when project-level rules change.

## Active Profile Layers

Profile-level content is managed separately from canonical experiences. Education, coursework, and skills live under `content/profile/`; skill categories live under `content/taxonomy/skill_categories.yaml`. Historical Interests entries are excluded from the active skills library and default resume generation.
