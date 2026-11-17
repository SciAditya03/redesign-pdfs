"""Structured analysis schemas.

Three stage schemas (content, design, comparative) are sent to Gemini as response schemas and
validated locally. Every field is *required* (nullable where information may legitimately be
unknown) so that missing information shows up as an explicit `null` / empty list rather than
being silently filled by a default.
"""

import re
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

SCHEMA_VERSION = "1.0"

Confidence = Literal["high", "medium", "low"]
Basis = Literal["observed", "inferred"]
Severity = Literal["high", "medium", "low"]
Depth = Literal["standard", "deep"]

_HEX_RE = re.compile(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


class _Model(BaseModel):
    model_config = ConfigDict(extra="ignore")


class Evidence(_Model):
    page: Optional[int] = Field(description="1-based page number in the relevant PDF, or null if document-wide.")
    observation: str = Field(description="What was seen on the page.")
    basis: Basis = Field(description="'observed' if directly visible, 'inferred' if deduced.")
    confidence: Confidence
    notes: Optional[str]


# ---------------------------------------------------------------- content authority

class DocumentMetadata(_Model):
    title: Optional[str] = Field(description="Exact document title as printed, or null if none is printed.")
    document_type: str = Field(description="e.g. catalogue, report, brochure, manual, paper.")
    purpose: str
    language: str
    page_count: int
    executive_summary: str = Field(description="Neutral summary for orientation only; never a replacement for source text.")


class Section(_Model):
    name: str = Field(description="Heading exactly as printed.")
    level: int = Field(description="1 = top-level section, 2 = subsection, …")
    parent: Optional[str] = Field(description="Name of the parent section, or null for top level.")
    start_page: int
    end_page: int
    content_types: list[str] = Field(description="e.g. paragraphs, bullet list, table, figure, callout.")
    approx_word_count: Optional[int]
    structural_notes: Optional[str]
    preservation_risks: list[str]


class ContentPage(_Model):
    page: int
    summary: str
    content_types: list[str]
    density: Literal["low", "medium", "high"]
    has_tables: bool
    has_figures: bool
    small_or_hard_to_read_text: bool
    appears_scanned: bool
    notes: Optional[str]


class ContentItem(_Model):
    kind: Literal[
        "heading", "paragraph_group", "list", "table", "figure", "chart", "diagram", "caption",
        "footnote", "reference", "note", "disclaimer", "numerical_data", "contact_info", "other",
    ]
    page: int
    label: str = Field(description="Short identifying label, e.g. the heading text or 'Table 2'.")
    detail: Optional[str]


class TableEntry(_Model):
    id: str = Field(description="Stable id, e.g. T1.")
    page: int
    title: Optional[str]
    columns: list[str] = Field(description="Column headers exactly as printed.")
    row_count: Optional[int]
    notes: Optional[str]
    extraction_confidence: Confidence


class FigureEntry(_Model):
    id: str = Field(description="Stable id, e.g. F1.")
    page: int
    kind: Literal["photo", "illustration", "chart", "diagram", "logo", "icon", "other"]
    caption: Optional[str] = Field(description="Caption exactly as printed, or null.")
    description: str


class NumericalItem(_Model):
    page: int
    value: str = Field(description="Value exactly as printed, including units.")
    context: str


class Term(_Model):
    term: str = Field(description="Exactly as printed, including capitalisation and italics notes.")
    category: Literal["scientific", "technical", "product", "abbreviation", "other"]
    pages: list[int]
    notes: Optional[str]


class ReferenceItem(_Model):
    page: int
    kind: Literal["footnote", "citation", "reference_list_entry", "cross_reference", "url", "other"]
    excerpt: str


class PreservationRisk(_Model):
    page: Optional[int]
    area: str
    risk: str
    severity: Severity
    mitigation: str


class ManualCheck(_Model):
    page: Optional[int]
    item: str
    reason: str


class ContentAnalysis(_Model):
    document_metadata: DocumentMetadata
    sections: list[Section]
    page_inventory: list[ContentPage] = Field(description="One entry per page (deep analysis) or for representative pages (standard).")
    content_inventory: list[ContentItem]
    tables: list[TableEntry]
    figures: list[FigureEntry]
    numerical_data: list[NumericalItem]
    terminology: list[Term]
    references: list[ReferenceItem]
    repeated_information: list[str]
    preservation_risks: list[PreservationRisk]
    manual_verification: list[ManualCheck] = Field(description="Anything that could not be extracted confidently.")
    evidence: list[Evidence]


# ---------------------------------------------------------------- design authority

class VisualIdentity(_Model):
    summary: str
    mood: list[str]
    brand_elements: list[str] = Field(description="Recurring visual devices (not text content).")
    contrast_notes: str


class Colour(_Model):
    name: str
    hex: Optional[str] = Field(description="#RRGGBB if reasonably inferable, else null.")
    role: Literal["primary", "secondary", "accent", "background", "surface", "text", "border", "other"]
    usage: str
    is_estimate: bool
    pages: list[int]

    @field_validator("hex")
    @classmethod
    def _normalise_hex(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v.strip() == "":
            return None
        m = _HEX_RE.match(v.strip())
        if not m:
            raise ValueError(f"'{v}' is not a #RRGGBB colour")
        h = m.group(1)
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        return "#" + h.upper()


class TypeLevel(_Model):
    level: str = Field(description="e.g. display, H1, H2, H3, body, caption, label, table header.")
    usage: str
    font_characteristics: str = Field(description="Classification (e.g. geometric sans) — not a claimed font name.")
    relative_size: str = Field(description="Relative or estimated pt size; say 'estimate' when estimated.")
    weight: str
    case: str
    letter_spacing: str
    line_spacing: str
    colour_role: Optional[str]


class Typography(_Model):
    heading_font_characteristics: str
    body_font_characteristics: str
    label_caption_characteristics: str
    possible_font_matches: list[str] = Field(description="Candidate fonts; empty if not identifiable.")
    font_identification_confidence: Confidence
    hierarchy: list[TypeLevel]
    alignment: str
    notes: Optional[str]


class PageGeometry(_Model):
    page_size: str = Field(description="e.g. A4, US Letter, custom.")
    width_mm: Optional[float]
    height_mm: Optional[float]
    orientation: Literal["portrait", "landscape", "mixed"]
    margins: str
    column_structure: str
    grid_system: str
    content_width: str
    header_height: Optional[str]
    footer_height: Optional[str]
    whitespace: str


class Component(_Model):
    name: str
    category: Literal[
        "cover", "section_opener", "card", "table", "highlight_panel", "callout", "image_block", "icon",
        "header", "footer", "section_number", "page_number", "divider", "list", "chart", "other",
    ]
    description: str
    visual_spec: str = Field(description="Colours, borders, radii, padding, type levels used.")
    usage_rules: str
    pages: list[int]


class PageArchetype(_Model):
    archetype: Literal[
        "cover", "contents", "introduction", "section_opener", "standard_content", "dense_technical",
        "table_heavy", "image_heavy", "comparison", "glossary", "appendix", "index", "back_cover", "other",
    ]
    label: str
    pages: list[int]
    layout_description: str
    key_components: list[str]
    content_capacity: str = Field(description="How much content this layout comfortably holds.")


class DesignPage(_Model):
    page: int
    archetype: str
    notes: Optional[str]


class DesignAnalysis(_Model):
    visual_identity: VisualIdentity
    colour_palette: list[Colour]
    typography: Typography
    page_geometry: PageGeometry
    components: list[Component]
    page_archetypes: list[PageArchetype]
    page_inventory: list[DesignPage]
    image_guidelines: list[str]
    evidence: list[Evidence]
    uncertainties: list[str]


# ---------------------------------------------------------------- comparative

class Mapping(_Model):
    content_element: str
    source_pages: list[int]
    recommended_treatment: str
    archetype: str
    component: Optional[str]
    rationale: str


class RedesignStrategy(_Model):
    overview: str
    typography_rules: list[str]
    colour_rules: list[str]
    spacing_rules: list[str]
    image_guidance: list[str]
    table_guidance: list[str]
    header_footer_rules: list[str]
    component_system: list[str]
    content_preservation_strategy: list[str]
    quality_control_strategy: list[str]


class ArchitectureEntry(_Model):
    order: int
    page_role: str
    archetype: str
    content: str = Field(description="Which content goes here (by section name / source page) — not rewritten text.")
    source_pages: list[int]
    notes: Optional[str]


class QualityRequirement(_Model):
    check: str
    description: str
    priority: Severity


class ComparativeAnalysis(_Model):
    content_to_design_mapping: list[Mapping]
    redesign_strategy: RedesignStrategy
    proposed_architecture: list[ArchitectureEntry]
    quality_requirements: list[QualityRequirement]
    conflicts_and_tradeoffs: list[str]


# ---------------------------------------------------------------- combined

class SourceDocument(_Model):
    role: Literal["content_authority", "design_authority"]
    filename: str
    page_count: int
    size_bytes: int


class ProjectInfo(_Model):
    id: str
    depth: Depth
    created_at: str
    documents: list[SourceDocument]


class StageMetadata(_Model):
    stage: str
    attempts: int
    duration_seconds: float
    finish_reason: Optional[str]
    input_tokens: Optional[int]
    output_tokens: Optional[int]
    schema_mode: Literal["constrained", "json_only"]


class GenerationMetadata(_Model):
    provider: Literal["google-gemini"] = "google-gemini"
    model: str
    sdk: str
    schema_version: str = SCHEMA_VERSION
    started_at: str
    completed_at: str
    stages: list[StageMetadata]


class AnalysisResult(_Model):
    project: ProjectInfo
    content_analysis: ContentAnalysis
    design_analysis: DesignAnalysis
    comparative_analysis: ComparativeAnalysis
    generation_metadata: GenerationMetadata
