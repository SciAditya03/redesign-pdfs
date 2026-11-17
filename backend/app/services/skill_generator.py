"""Convert a validated AnalysisResult into a self-contained Claude Skill package.

Package layout (inside the ZIP):
    document-redesign-specialist/
        SKILL.md
        DESIGN_ANALYSIS.md
        CONTENT_STRUCTURE.md
        REDESIGN_STRATEGY.md
        QUALITY_CHECKLIST.md
        analysis.json
"""

from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from typing import Iterable

from app.schemas.analysis import AnalysisResult

SKILL_NAME = "document-redesign-specialist"
SKILL_DESCRIPTION = (
    "Redesign a content-authority PDF using a separate design-authority PDF while preserving all original "
    "content and applying the reference document's visual language."
)
REQUIRED_FILES = (
    "SKILL.md",
    "DESIGN_ANALYSIS.md",
    "CONTENT_STRUCTURE.md",
    "REDESIGN_STRATEGY.md",
    "QUALITY_CHECKLIST.md",
    "analysis.json",
)
OUTPUT_KEYS = ("skill_zip", "skill_md", "analysis_json")

_NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


class SkillGenerationError(RuntimeError):
    pass


# ---------------------------------------------------------------- markdown helpers

def _inline(value: object) -> str:
    """Single-line text safe for Markdown paragraphs and list items."""
    if value is None:
        return "—"
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or "—"


def _cell(value: object) -> str:
    """Text safe inside a Markdown table cell."""
    return _inline(value).replace("\\", "\\\\").replace("|", "\\|")


def _pages(pages: Iterable[int] | None) -> str:
    nums = sorted({int(p) for p in (pages or [])})
    if not nums:
        return "—"
    ranges, start, prev = [], nums[0], nums[0]
    for n in nums[1:]:
        if n == prev + 1:
            prev = n
            continue
        ranges.append(f"{start}–{prev}" if start != prev else str(start))
        start = prev = n
    ranges.append(f"{start}–{prev}" if start != prev else str(start))
    return ", ".join(ranges)


def _table(headers: list[str], rows: list[list[object]]) -> str:
    if not rows:
        return "_None recorded._\n"
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for row in rows:
        out.append("| " + " | ".join(_cell(c) for c in row) + " |")
    return "\n".join(out) + "\n"


def _bullets(items: Iterable[object]) -> str:
    items = [i for i in items if i is not None and str(i).strip()]
    if not items:
        return "_None recorded._\n"
    return "\n".join(f"- {_inline(i)}" for i in items) + "\n"


def _docs(a: AnalysisResult) -> tuple[str, str]:
    content = next(d for d in a.project.documents if d.role == "content_authority")
    design = next(d for d in a.project.documents if d.role == "design_authority")
    return (
        f"`{_cell(content.filename)}` ({content.page_count} pages)",
        f"`{_cell(design.filename)}` ({design.page_count} pages)",
    )


# ---------------------------------------------------------------- SKILL.md

def render_skill_md(a: AnalysisResult) -> str:
    ca, da, cmp = a.content_analysis, a.design_analysis, a.comparative_analysis
    content_doc, design_doc = _docs(a)
    meta = ca.document_metadata

    palette = _table(
        ["Role", "Name", "HEX", "Estimate?", "Usage"],
        [[c.role, c.name, c.hex or "not inferable", "yes" if c.is_estimate else "no", c.usage] for c in da.colour_palette],
    )
    type_levels = _table(
        ["Level", "Characteristics", "Size", "Weight", "Case / spacing", "Usage"],
        [
            [t.level, t.font_characteristics, t.relative_size, t.weight, f"{t.case}; tracking {t.letter_spacing}; leading {t.line_spacing}", t.usage]
            for t in da.typography.hierarchy
        ],
    )
    archetypes = _table(
        ["Archetype", "Label", "Reference pages", "Layout"],
        [[p.archetype, p.label, _pages(p.pages), p.layout_description] for p in da.page_archetypes],
    )
    architecture = _table(
        ["#", "Page role", "Archetype", "Content (by source section)", "Source pages"],
        [[e.order, e.page_role, e.archetype, e.content, _pages(e.source_pages)] for e in sorted(cmp.proposed_architecture, key=lambda e: e.order)],
    )
    fonts = ", ".join(da.typography.possible_font_matches) or "not identified"
    geo = da.page_geometry

    return f"""---
name: {SKILL_NAME}
description: {SKILL_DESCRIPTION}
---

# Document Redesign Specialist

Use this Skill to redesign a **content-authority PDF** in the visual language of a separate **design-authority PDF**,
preserving every piece of original content. The analysis in this package was produced by Google Gemini
({_inline(a.generation_metadata.model)}, {a.project.depth} analysis, {a.generation_metadata.completed_at}).
Treat it as a strong starting point, and verify it against the PDFs themselves.

## 1. Document roles (never confuse them)

| Role | File analysed | What it governs |
|---|---|---|
| **Content authority** | {content_doc} | Every word, heading, number, table, caption, reference and the section hierarchy. Single source of truth. |
| **Design authority** | {design_doc} | Colour, typography, geometry, components, page archetypes. Visual rules only; **its text is never copied**. |

The user should upload both original PDFs with this Skill. If the filenames differ from those above, identify each
role by page count and by the title and structure described in `CONTENT_STRUCTURE.md` (content) and
`DESIGN_ANALYSIS.md` (design). If you cannot tell which is which, ask the user before doing anything else.

Content document: **{_inline(meta.title)}**, a {_inline(meta.document_type)} with {meta.page_count} pages,
{len(ca.sections)} sections and subsections, {len(ca.tables)} tables and {len(ca.figures)} figures.

## 2. Content preservation rules (non-negotiable)

- Preserve every fact, sentence, heading, list item and technical detail from the content authority.
- Preserve all numerical values exactly, including units, ranges, ±, decimals, superscripts and subscripts.
- Preserve scientific names (including italics), product names, abbreviations and terminology exactly.
- Preserve every table: all rows, columns, headers, merged-cell meaning and footnotes.
- Preserve figures with their exact captions, and all references, footnotes, notes and disclaimers.
- Preserve the section hierarchy and order unless `REDESIGN_STRATEGY.md` explicitly justifies a regrouping, and even then no content may be lost.
- **Do not summarise, paraphrase, shorten, omit or invent content** unless the user explicitly authorises it.
- Never introduce text, images, logos or data from the design authority into the redesigned document.
- Where the analysis flags `manual_verification` items (see `CONTENT_STRUCTURE.md`), read them from the PDF yourself and report any you cannot resolve.

## 3. Design language to apply

Visual identity: {_inline(da.visual_identity.summary)}

### Colour palette
{palette}
Values marked as estimates were inferred from the reference rendering. Sample the reference PDF to refine them if your tools allow it.

### Typography
- Headings: {_inline(da.typography.heading_font_characteristics)}
- Body: {_inline(da.typography.body_font_characteristics)}
- Labels and captions: {_inline(da.typography.label_caption_characteristics)}
- Possible font matches: {_inline(fonts)} (identification confidence: {da.typography.font_identification_confidence}). If these fonts are not available, choose the closest available fonts with the same classification, and use them consistently.

{type_levels}
### Page geometry
{_inline(geo.page_size)}, {geo.orientation}{f", {geo.width_mm} × {geo.height_mm} mm" if geo.width_mm and geo.height_mm else ""}.
Margins: {_inline(geo.margins)}. Columns: {_inline(geo.column_structure)}. Grid: {_inline(geo.grid_system)}.

### Page archetypes in the reference
{archetypes}
Full component specifications, evidence and uncertainties are in `DESIGN_ANALYSIS.md`.

Apply the reference's *design principles* consistently. Do not copy its content, and do not experiment with
layouts outside this system. Reuse the same components for the same kinds of content throughout.

## 4. Plan before you lay anything out

1. Open both PDFs and inspect them page by page. Confirm (or correct) the analysis in this package.
2. Build a **content inventory** from the content authority: every section, paragraph group, list, table, figure, caption, note and reference, with source page numbers. `CONTENT_STRUCTURE.md` is your starting checklist.
3. Build a **design inventory** from the design authority: tokens, type levels, components and archetypes (see `DESIGN_ANALYSIS.md`).
4. Map each content block to an archetype and component, using `REDESIGN_STRATEGY.md`.
5. Fix the complete document structure (page sequence, section openers, running headers and footers, numbering) **before** producing any layout. The proposed architecture is:

{architecture}
## 5. Execute the redesign

Use whatever document-generation capabilities you have in the current environment. This Skill does not assume any
particular PDF tool. Typical workflows include HTML/CSS rendered to PDF, a programmatic PDF library, or a
DOCX/PPTX build exported to PDF. Choose one that can:

- hold the design tokens (colours, type scale, spacing) in one place and apply them everywhere;
- place the content text programmatically from your inventory, never by retyping it from memory;
- render tables as real tables, and keep captions attached to their figures;
- produce running headers, footers and real page numbers.

Create intermediate outputs (for example, a structured content file and a template) when they help you guarantee completeness.
Render a draft, inspect it page by page, fix any issues, then produce the final PDF.

## 6. Validate the result

Work through `QUALITY_CHECKLIST.md` and confirm at least the following:
- every source page and section is represented, in order;
- every table is complete, with no missing rows, columns or footnotes;
- every number, unit and scientific term matches the source exactly;
- figures and captions are present and correctly paired;
- typography and colours follow the design rules on every page;
- alignment and spacing are consistent; there is no clipped or overflowing text, and no orphaned headings;
- headers, footers and page numbering are correct throughout.

Where possible, extract the text of your output and compare it with the source text to find omissions.

## 7. Deliver

1. The redesigned PDF.
2. A short quality-control report: the checks performed, their results, and any deviations from the design system with the reason for each.
3. A list of unresolved content-preservation issues, each with a source page number (for example, illegible source text or ambiguous table structure).

## Files in this Skill

- `DESIGN_ANALYSIS.md`: full design-authority analysis with page evidence.
- `CONTENT_STRUCTURE.md`: section hierarchy, page inventory, tables, figures, terminology and preservation risks.
- `REDESIGN_STRATEGY.md`: content-to-design mapping, rules and the proposed architecture.
- `QUALITY_CHECKLIST.md`: the checks to complete before delivery.
- `analysis.json`: the complete structured analysis (machine-readable).
"""


# ---------------------------------------------------------------- supporting files

def render_design_md(a: AnalysisResult) -> str:
    da = a.design_analysis
    vi, ty, geo = da.visual_identity, da.typography, da.page_geometry
    _, design_doc = _docs(a)
    return f"""# Design Analysis — Design Authority

Source: {design_doc}. This document describes **visual language only**.

## Visual identity
{_inline(vi.summary)}

- Mood: {_inline(", ".join(vi.mood))}
- Contrast: {_inline(vi.contrast_notes)}

Recurring brand elements:
{_bullets(vi.brand_elements)}
## Colour palette
{_table(["Role", "Name", "HEX", "Estimate?", "Usage", "Pages"], [[c.role, c.name, c.hex or "not inferable", "yes" if c.is_estimate else "no", c.usage, _pages(c.pages)] for c in da.colour_palette])}
## Typography
- Heading characteristics: {_inline(ty.heading_font_characteristics)}
- Body characteristics: {_inline(ty.body_font_characteristics)}
- Label/caption characteristics: {_inline(ty.label_caption_characteristics)}
- Possible font matches: {_inline(", ".join(ty.possible_font_matches) or "not identified")} (confidence: {ty.font_identification_confidence})
- Alignment: {_inline(ty.alignment)}
- Notes: {_inline(ty.notes)}

{_table(["Level", "Characteristics", "Relative size", "Weight", "Case", "Letter spacing", "Line spacing", "Colour", "Usage"], [[t.level, t.font_characteristics, t.relative_size, t.weight, t.case, t.letter_spacing, t.line_spacing, t.colour_role, t.usage] for t in ty.hierarchy])}
## Page geometry
{_table(["Property", "Value"], [["Page size", geo.page_size], ["Dimensions", f"{geo.width_mm} × {geo.height_mm} mm" if geo.width_mm and geo.height_mm else None], ["Orientation", geo.orientation], ["Margins", geo.margins], ["Columns", geo.column_structure], ["Grid", geo.grid_system], ["Content width", geo.content_width], ["Header height", geo.header_height], ["Footer height", geo.footer_height], ["White space", geo.whitespace]])}
## Components
""" + "\n".join(
        f"""### {_inline(c.name)} ({c.category})
- Reference pages: {_pages(c.pages)}
- Description: {_inline(c.description)}
- Visual spec: {_inline(c.visual_spec)}
- Usage rules: {_inline(c.usage_rules)}
"""
        for c in da.components
    ) + f"""
## Page archetypes
{_table(["Archetype", "Label", "Pages", "Layout", "Key components", "Capacity"], [[p.archetype, p.label, _pages(p.pages), p.layout_description, ", ".join(p.key_components), p.content_capacity] for p in da.page_archetypes])}
## Page inventory
{_table(["Page", "Archetype", "Notes"], [[p.page, p.archetype, p.notes] for p in sorted(da.page_inventory, key=lambda p: p.page)])}
## Image and illustration guidelines
{_bullets(da.image_guidelines)}
## Evidence
{_table(["Page", "Observation", "Basis", "Confidence", "Notes"], [[e.page, e.observation, e.basis, e.confidence, e.notes] for e in da.evidence])}
## Uncertainties
{_bullets(da.uncertainties)}"""


def render_content_md(a: AnalysisResult) -> str:
    ca = a.content_analysis
    m = ca.document_metadata
    content_doc, _ = _docs(a)
    return f"""# Content Structure — Content Authority

Source: {content_doc}. Everything in the source document must be preserved. This file is an inventory to check
completeness against; it is **not** a substitute for the source text.

## Document
{_table(["Property", "Value"], [["Title", m.title], ["Type", m.document_type], ["Purpose", m.purpose], ["Language", m.language], ["Pages", m.page_count]])}
Orientation summary (not for reuse as content): {_inline(m.executive_summary)}

## Section hierarchy
{_table(["Level", "Section (as printed)", "Parent", "Pages", "Content types", "≈ Words", "Notes", "Risks"], [[s.level, s.name, s.parent, _pages(range(s.start_page, s.end_page + 1)), ", ".join(s.content_types), s.approx_word_count, s.structural_notes, "; ".join(s.preservation_risks)] for s in ca.sections])}
## Page inventory
{_table(["Page", "Density", "Content types", "Tables", "Figures", "Small text", "Scanned", "Summary", "Notes"], [[p.page, p.density, ", ".join(p.content_types), "yes" if p.has_tables else "", "yes" if p.has_figures else "", "yes" if p.small_or_hard_to_read_text else "", "yes" if p.appears_scanned else "", p.summary, p.notes] for p in sorted(ca.page_inventory, key=lambda p: p.page)])}
## Content inventory
{_table(["Page", "Kind", "Label", "Detail"], [[c.page, c.kind, c.label, c.detail] for c in sorted(ca.content_inventory, key=lambda c: c.page)])}
## Tables
{_table(["ID", "Page", "Title", "Columns", "Rows", "Confidence", "Notes"], [[t.id, t.page, t.title, "; ".join(t.columns), t.row_count, t.extraction_confidence, t.notes] for t in ca.tables])}
## Figures
{_table(["ID", "Page", "Kind", "Caption (as printed)", "Description"], [[f.id, f.page, f.kind, f.caption, f.description] for f in ca.figures])}
## Numerical data to verify
{_table(["Page", "Value", "Context"], [[n.page, n.value, n.context] for n in ca.numerical_data])}
## Terminology
{_table(["Term", "Category", "Pages", "Notes"], [[t.term, t.category, _pages(t.pages), t.notes] for t in ca.terminology])}
## References, footnotes and links
{_table(["Page", "Kind", "Excerpt"], [[r.page, r.kind, r.excerpt] for r in ca.references])}
## Repeated information
{_bullets(ca.repeated_information)}
## Preservation risks
{_table(["Page", "Area", "Risk", "Severity", "Mitigation"], [[r.page, r.area, r.risk, r.severity, r.mitigation] for r in ca.preservation_risks])}
## Requires manual verification
{_table(["Page", "Item", "Reason"], [[v.page, v.item, v.reason] for v in ca.manual_verification])}
## Evidence
{_table(["Page", "Observation", "Basis", "Confidence", "Notes"], [[e.page, e.observation, e.basis, e.confidence, e.notes] for e in ca.evidence])}"""


def render_strategy_md(a: AnalysisResult) -> str:
    cmp = a.comparative_analysis
    s = cmp.redesign_strategy
    return f"""# Redesign Strategy

{_inline(s.overview)}

## Content-to-design mapping
This mapping is guidance. Prioritise readability and accuracy over decoration.

{_table(["Content element", "Source pages", "Treatment", "Archetype", "Component", "Rationale"], [[m.content_element, _pages(m.source_pages), m.recommended_treatment, m.archetype, m.component, m.rationale] for m in cmp.content_to_design_mapping])}
## Proposed document architecture
{_table(["#", "Page role", "Archetype", "Content", "Source pages", "Notes"], [[e.order, e.page_role, e.archetype, e.content, _pages(e.source_pages), e.notes] for e in sorted(cmp.proposed_architecture, key=lambda e: e.order)])}
## Rules
### Typography
{_bullets(s.typography_rules)}
### Colour
{_bullets(s.colour_rules)}
### Spacing
{_bullets(s.spacing_rules)}
### Images and illustrations
{_bullets(s.image_guidance)}
### Tables
{_bullets(s.table_guidance)}
### Headers and footers
{_bullets(s.header_footer_rules)}
### Component system
{_bullets(s.component_system)}
## Content-preservation strategy
{_bullets(s.content_preservation_strategy)}
## Quality-control strategy
{_bullets(s.quality_control_strategy)}
## Conflicts and trade-offs
{_bullets(cmp.conflicts_and_tradeoffs)}"""


BASELINE_CHECKS = [
    ("Page completeness", "Every source page's content appears in the redesign, in order."),
    ("Section completeness", "Every section and subsection in CONTENT_STRUCTURE.md is present with its exact heading."),
    ("Table completeness", "Every table has all rows, columns, headers and footnotes."),
    ("Numerical accuracy", "Every number, unit, range and symbol matches the source exactly."),
    ("Terminology", "Scientific names, abbreviations and product names are spelled and styled exactly as in the source."),
    ("Figures and captions", "Every figure is present and paired with its exact caption."),
    ("No foreign content", "No text, logos or images were taken from the design authority."),
    ("Typography", "Type levels follow the design system consistently on every page."),
    ("Colour", "Only palette colours are used, in their documented roles."),
    ("Alignment and grid", "Elements align to the grid; margins are consistent."),
    ("Overflow and clipping", "No text is clipped, overflowing or hidden; there are no orphaned headings."),
    ("Headers and footers", "Running headers and footers are correct on every page."),
    ("Page numbering", "Page numbers are sequential and match the contents page, if one exists."),
    ("Manual verification items", "Every item listed under 'Requires manual verification' is resolved or reported."),
]


def render_checklist_md(a: AnalysisResult) -> str:
    ca, cmp = a.content_analysis, a.comparative_analysis
    lines = ["# Quality Checklist", "", "Complete every item before delivering the redesigned PDF.", "", "## Baseline checks", ""]
    lines += [f"- [ ] **{name}**: {desc}" for name, desc in BASELINE_CHECKS]
    lines += ["", "## Document-specific requirements", ""]
    order = {"high": 0, "medium": 1, "low": 2}
    reqs = sorted(cmp.quality_requirements, key=lambda q: order[q.priority])
    lines += [f"- [ ] **{_inline(q.check)}** ({q.priority}): {_inline(q.description)}" for q in reqs] or ["_None recorded._"]
    lines += ["", "## Tables to verify", ""]
    lines += [f"- [ ] {_inline(t.id)} (page {t.page}): {_inline(t.title)}, {t.row_count if t.row_count is not None else '?'} rows" for t in ca.tables] or ["_No tables recorded._"]
    lines += ["", "## Figures to verify", ""]
    lines += [f"- [ ] {_inline(f.id)} (page {f.page}): caption: {_inline(f.caption)}" for f in ca.figures] or ["_No figures recorded._"]
    lines += ["", "## High-severity preservation risks", ""]
    high = [r for r in ca.preservation_risks if r.severity == "high"]
    lines += [f"- [ ] Page {r.page if r.page is not None else '—'}, {_inline(r.area)}: {_inline(r.risk)} → {_inline(r.mitigation)}" for r in high] or ["_None recorded._"]
    lines += ["", "## Manual verification", ""]
    lines += [f"- [ ] Page {v.page if v.page is not None else '—'}: {_inline(v.item)} ({_inline(v.reason)})" for v in ca.manual_verification] or ["_None recorded._"]
    lines += ["", "## Quality-control report template", "", "```text",
              "Checks performed: …", "Result per check: pass / fail + notes", "Deviations from design system: …",
              "Unresolved content issues (page, item, reason): …", "```", ""]
    return "\n".join(lines)


# ---------------------------------------------------------------- build

def render_files(a: AnalysisResult) -> dict[str, str]:
    files = {
        "SKILL.md": render_skill_md(a),
        "DESIGN_ANALYSIS.md": render_design_md(a),
        "CONTENT_STRUCTURE.md": render_content_md(a),
        "REDESIGN_STRATEGY.md": render_strategy_md(a),
        "QUALITY_CHECKLIST.md": render_checklist_md(a),
        "analysis.json": json.dumps(a.model_dump(mode="json"), ensure_ascii=False, indent=2),
    }
    validate_skill_md(files["SKILL.md"])
    missing = [f for f in REQUIRED_FILES if not files.get(f)]
    if missing:
        raise SkillGenerationError(f"Skill files missing: {missing}")
    return files


def parse_frontmatter(skill_md: str) -> dict[str, str]:
    """Minimal YAML-frontmatter parser for the flat key: value block a Skill uses."""
    if not skill_md.startswith("---\n"):
        raise SkillGenerationError("SKILL.md must start with YAML frontmatter")
    end = skill_md.find("\n---\n", 4)
    if end == -1:
        raise SkillGenerationError("SKILL.md frontmatter is not closed")
    data = {}
    for line in skill_md[4:end].splitlines():
        if not line.strip():
            continue
        key, sep, value = line.partition(":")
        if not sep:
            raise SkillGenerationError(f"Invalid frontmatter line: {line!r}")
        data[key.strip()] = value.strip()
    return data


def validate_skill_md(skill_md: str) -> None:
    fm = parse_frontmatter(skill_md)
    if set(fm) != {"name", "description"}:
        raise SkillGenerationError(f"Frontmatter must contain exactly name and description, got {sorted(fm)}")
    if not _NAME_RE.fullmatch(fm["name"]) or len(fm["name"]) > 64:
        raise SkillGenerationError("Skill name must be lowercase letters, digits and hyphens (max 64)")
    desc = fm["description"]
    if not desc or len(desc) > 1024 or any(ch in desc for ch in "<>"):
        raise SkillGenerationError("Skill description must be 1-1024 characters without angle brackets")
    # A colon followed by a space would turn the YAML scalar into a mapping.
    if ": " in desc or desc.startswith(("'", '"', "[", "{", "&", "*", "!", "|", ">", "%", "@", "`")):
        raise SkillGenerationError("Skill description is not a safe plain YAML scalar")


def build_outputs(analysis: AnalysisResult, outputs: list[str], project_dir: Path) -> dict[str, str]:
    """Write requested outputs into `project_dir`. Returns {output_key: relative_path}."""
    unknown = set(outputs) - set(OUTPUT_KEYS)
    if unknown or not outputs:
        raise SkillGenerationError(f"Invalid outputs: {sorted(unknown) or 'none selected'}")
    files = render_files(analysis)
    written: dict[str, str] = {}

    skill_dir = project_dir / "skill" / SKILL_NAME
    skill_dir.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (skill_dir / name).write_text(text, encoding="utf-8", newline="\n")

    if "skill_md" in outputs:
        written["skill_md"] = f"skill/{SKILL_NAME}/SKILL.md"
    if "analysis_json" in outputs:
        written["analysis_json"] = "analysis.json"
    if "skill_zip" in outputs:
        zip_path = project_dir / f"{SKILL_NAME}.zip"
        tmp = zip_path.with_suffix(".zip.tmp")
        with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for name in REQUIRED_FILES:
                zf.writestr(f"{SKILL_NAME}/{name}", files[name])
        tmp.replace(zip_path)
        verify_zip(zip_path)
        written["skill_zip"] = zip_path.name
    return written


def verify_zip(zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path) as zf:
        if zf.testzip() is not None:
            raise SkillGenerationError("Generated ZIP is corrupt")
        names = set(zf.namelist())
        missing = [f for f in REQUIRED_FILES if f"{SKILL_NAME}/{f}" not in names]
        if missing:
            raise SkillGenerationError(f"ZIP is missing {missing}")
        validate_skill_md(zf.read(f"{SKILL_NAME}/SKILL.md").decode("utf-8"))
