"""Prompts for the three Gemini analysis stages."""

import json

from app.schemas.analysis import Depth

SYSTEM_INSTRUCTION = """You are a meticulous document-intelligence analyst working for a document redesign pipeline.
You receive original PDF files and must report only what the documents support.

Two document roles exist and must never be confused:
- CONTENT AUTHORITY PDF: the single source of truth for text, headings, terminology, scientific names,
  numbers, tables, captions, references, section hierarchy, notes and disclaimers. Its content will be preserved
  verbatim in a redesign.
- DESIGN AUTHORITY PDF: a visual reference only. It defines colours, typography, geometry, components and page
  archetypes. Its textual content must never be treated as content for the redesign.

Rules:
- Never invent content, values, fonts or colours. If something cannot be determined, use null, an empty list,
  or record it in the uncertainty / manual-verification fields.
- Quote headings, terms, values and captions exactly as printed.
- Page numbers are 1-based physical page indices of the PDF file (not printed folios).
- Distinguish what you directly observed from what you inferred, and give honest confidence levels.
- Return only JSON conforming to the response schema."""

_DEPTH_CONTENT = {
    "deep": (
        "DEPTH: DEEP. Analyse at both document-wide and page level. `page_inventory` must contain exactly one entry "
        "for EVERY page of the content PDF, in order. List every table, every figure, and every distinct section and "
        "subsection. Record numerical values that are formatting-sensitive (units, ranges, ±, superscripts)."
    ),
    "standard": (
        "DEPTH: STANDARD. Analyse at document level. `page_inventory` may cover representative pages only "
        "(cover, each section start, and any unusual pages). Still list every top-level section, every table and "
        "every figure."
    ),
}

_DEPTH_DESIGN = {
    "deep": (
        "DEPTH: DEEP. Inspect every page. `page_inventory` must contain one entry for EVERY page of the design PDF "
        "with its archetype. Provide page-cited evidence for every colour, type level, component and archetype."
    ),
    "standard": (
        "DEPTH: STANDARD. Inspect the document as a whole plus representative pages. `page_inventory` may cover "
        "representative pages only. Provide page-cited evidence for key observations."
    ),
}


def content_prompt(depth: Depth, filename: str, page_count: int) -> str:
    return f"""TASK: Content Authority analysis.

The attached PDF ("{filename}", {page_count} pages) is the CONTENT AUTHORITY document.
{_DEPTH_CONTENT[depth]}

Extract and understand: title, purpose, executive summary, the full section/subsection hierarchy with page ranges
and approximate volume, paragraph structures, lists, tables (with exact column headers), figures/charts/diagrams
with exact captions, numerical information, scientific and technical terminology, footnotes, references, repeated
information, and formatting-sensitive content.

For every section record preservation risks. Identify dense-text pages, table-heavy pages, complex scientific
content, image+caption pages, small or hard-to-read text, scanned pages and likely OCR issues.
Anything you cannot extract confidently must appear in `manual_verification`. Never fill gaps with plausible text."""


def design_prompt(depth: Depth, filename: str, page_count: int) -> str:
    return f"""TASK: Design Authority analysis.

The attached PDF ("{filename}", {page_count} pages) is the DESIGN AUTHORITY document. Analyse its visual language
only. Do not extract or reproduce its textual content except short labels needed to identify a component.
{_DEPTH_DESIGN[depth]}

Cover:
- Visual identity: primary, secondary, accent, background, surface, text and border colours; contrast; colour usage
  patterns. Give #RRGGBB only when reasonably inferable and set `is_estimate` truthfully.
- Typography: heading/body/label/caption characteristics, weights, hierarchy with relative sizes, line and letter
  spacing, alignment. Do not claim an exact font name unless it is visually certain; use `possible_font_matches`
  and `font_identification_confidence`.
- Page geometry: size, orientation, margins, columns, grid, content width, header/footer heights, white space.
- Recurring components: covers, section openers, cards, tables, highlight panels, callouts, image blocks, icons,
  headers, footers, section numbers, page numbers, dividers.
- Page archetypes actually present in this document (only those it supports), with page numbers.
- Image and illustration treatment.
Record uncertainties explicitly."""


def comparative_prompt(depth: Depth, content_json: dict, design_json: dict) -> str:
    return f"""TASK: Comparative analysis and redesign strategy.

Two PDFs are attached: first the CONTENT AUTHORITY PDF, then the DESIGN AUTHORITY PDF.
Below are the validated analyses already produced for each. Use the PDFs to verify and refine, not to contradict
the analyses without reason.

Determine how the content document should be reorganised visually using the design reference:
- `content_to_design_mapping`: map each content structure (main sections, subsections, dense paragraphs, tables,
  important notes, numerical highlights, figures, repeated capabilities, …) to a visual treatment, archetype and
  component. This is guidance: never force content into decorative cards when a plain layout reads better.
- `redesign_strategy`: typography, colour, spacing, image, table and header/footer rules, the reusable component
  system, a content-preservation strategy and a quality-control strategy. Rules must be concrete and consistent
  across the whole document.
- `proposed_architecture`: the recommended page sequence of the redesigned document, each entry naming the
  archetype and which content (by section name and source page) it holds. Do not rewrite content.
- `quality_requirements`: checks a redesigner must pass (completeness, numerical accuracy, terminology, tables,
  figures/captions, typography, alignment, overflow, headers/footers, numbering).
- `conflicts_and_tradeoffs`: where the design language and the content do not fit naturally
  (e.g. content far denser than the reference layouts) and how to resolve it.

Readability and scientific accuracy take priority over decoration.
{_DEPTH_CONTENT[depth].split('.')[0]}.

CONTENT AUTHORITY ANALYSIS:
{json.dumps(content_json, ensure_ascii=False)}

DESIGN AUTHORITY ANALYSIS:
{json.dumps(design_json, ensure_ascii=False)}"""


def repair_prompt(errors: str) -> str:
    return f"""Your previous response could not be accepted because it failed schema validation:

{errors}

Return the COMPLETE corrected JSON object again. Fix only what is needed to satisfy the schema.
Where information is genuinely unknown use null or an empty list as the schema allows; do not invent values."""


def json_only_suffix(schema: dict) -> str:
    return (
        "\n\nRespond with a single JSON object that conforms exactly to this JSON Schema "
        f"(all properties required):\n{json.dumps(schema, ensure_ascii=False)}"
    )
