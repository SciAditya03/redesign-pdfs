"""Test data: tiny real PDFs and schema-valid Gemini stage outputs (used by the mocked Gemini client)."""

import pymupdf

from app.schemas.analysis import ComparativeAnalysis, ContentAnalysis, DesignAnalysis


def make_pdf(pages: int = 2, text: str = "Sample page", encrypted: bool = False) -> bytes:
    doc = pymupdf.open()
    for i in range(pages):
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 72), f"{text} {i + 1}. " + "Lorem ipsum dolor sit amet, consectetur adipiscing elit. " * 3, fontsize=11)
    kwargs = {}
    if encrypted:
        kwargs = dict(encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw="owner", user_pw="secret")
    data = doc.tobytes(**kwargs)
    doc.close()
    return data


def content_analysis() -> ContentAnalysis:
    return ContentAnalysis.model_validate({
        "document_metadata": {"title": "Assay Capabilities", "document_type": "catalogue", "purpose": "List assays", "language": "en", "page_count": 2, "executive_summary": "A catalogue of assays."},
        "sections": [
            {"name": "Introduction", "level": 1, "parent": None, "start_page": 1, "end_page": 1, "content_types": ["paragraphs"], "approx_word_count": 120, "structural_notes": None, "preservation_risks": []},
            {"name": "Proteomics | Mass Spec", "level": 1, "parent": None, "start_page": 2, "end_page": 2, "content_types": ["table"], "approx_word_count": 80, "structural_notes": "Pipe in heading", "preservation_risks": ["Dense table"]},
        ],
        "page_inventory": [
            {"page": 1, "summary": "Intro", "content_types": ["paragraphs"], "density": "medium", "has_tables": False, "has_figures": False, "small_or_hard_to_read_text": False, "appears_scanned": False, "notes": None},
            {"page": 2, "summary": "Table", "content_types": ["table"], "density": "high", "has_tables": True, "has_figures": False, "small_or_hard_to_read_text": True, "appears_scanned": False, "notes": None},
        ],
        "content_inventory": [{"kind": "heading", "page": 1, "label": "Introduction", "detail": None}],
        "tables": [{"id": "T1", "page": 2, "title": "Assays", "columns": ["Assay", "LOD (ng/mL)"], "row_count": 12, "notes": None, "extraction_confidence": "high"}],
        "figures": [],
        "numerical_data": [{"page": 2, "value": "0.5 ng/mL", "context": "LOD"}],
        "terminology": [{"term": "Escherichia coli", "category": "scientific", "pages": [1, 2], "notes": "italic"}],
        "references": [],
        "repeated_information": [],
        "preservation_risks": [{"page": 2, "area": "Table T1", "risk": "Small text", "severity": "high", "mitigation": "Verify every value"}],
        "manual_verification": [{"page": 2, "item": "Footnote marker", "reason": "Low resolution"}],
        "evidence": [{"page": 1, "observation": "Single-column intro", "basis": "observed", "confidence": "high", "notes": None}],
    })


def design_analysis() -> DesignAnalysis:
    return DesignAnalysis.model_validate({
        "visual_identity": {"summary": "Navy and green scientific brand", "mood": ["clinical", "precise"], "brand_elements": ["wave motif"], "contrast_notes": "High"},
        "colour_palette": [
            {"name": "Navy", "hex": "#191f5b", "role": "primary", "usage": "Headings", "is_estimate": True, "pages": [1, 2]},
            {"name": "Green", "hex": "079B4B", "role": "accent", "usage": "Rules", "is_estimate": True, "pages": [1]},
            {"name": "Photo tint", "hex": None, "role": "other", "usage": "Image overlay", "is_estimate": True, "pages": [1]},
        ],
        "typography": {
            "heading_font_characteristics": "Geometric sans, bold", "body_font_characteristics": "Humanist sans",
            "label_caption_characteristics": "Monospace caps", "possible_font_matches": ["Manrope"], "font_identification_confidence": "low",
            "hierarchy": [{"level": "H1", "usage": "Section titles", "font_characteristics": "Geometric sans", "relative_size": "~28pt estimate", "weight": "bold", "case": "sentence", "letter_spacing": "tight", "line_spacing": "1.1", "colour_role": "primary"}],
            "alignment": "left", "notes": None,
        },
        "page_geometry": {"page_size": "A4", "width_mm": 210, "height_mm": 297, "orientation": "portrait", "margins": "18 mm", "column_structure": "2 columns", "grid_system": "12-col", "content_width": "174 mm", "header_height": "12 mm", "footer_height": "10 mm", "whitespace": "Generous"},
        "components": [{"name": "Section opener band", "category": "section_opener", "description": "Full-bleed band", "visual_spec": "Navy band, white H1", "usage_rules": "Start of each section", "pages": [2]}],
        "page_archetypes": [{"archetype": "cover", "label": "Cover", "pages": [1], "layout_description": "Full-bleed image", "key_components": ["Title block"], "content_capacity": "Title only"}],
        "page_inventory": [{"page": 1, "archetype": "cover", "notes": None}, {"page": 2, "archetype": "section_opener", "notes": None}],
        "image_guidelines": ["Duotone photography"],
        "evidence": [{"page": 1, "observation": "Navy cover", "basis": "observed", "confidence": "high", "notes": None}],
        "uncertainties": ["Exact font unknown"],
    })


def comparative_analysis() -> ComparativeAnalysis:
    return ComparativeAnalysis.model_validate({
        "content_to_design_mapping": [{"content_element": "Main section", "source_pages": [1, 2], "recommended_treatment": "Section opener", "archetype": "section_opener", "component": "Section opener band", "rationale": "Matches reference"}],
        "redesign_strategy": {
            "overview": "Apply navy/green system.", "typography_rules": ["H1 bold"], "colour_rules": ["Navy for headings"], "spacing_rules": ["8 pt baseline"],
            "image_guidance": ["Duotone"], "table_guidance": ["Zebra rows"], "header_footer_rules": ["Running footer"], "component_system": ["Cards for assays"],
            "content_preservation_strategy": ["Place text programmatically"], "quality_control_strategy": ["Text diff"],
        },
        "proposed_architecture": [
            {"order": 2, "page_role": "Introduction", "archetype": "introduction", "content": "Introduction", "source_pages": [1], "notes": None},
            {"order": 1, "page_role": "Cover", "archetype": "cover", "content": "Title", "source_pages": [1], "notes": None},
        ],
        "quality_requirements": [{"check": "LOD values", "description": "All LODs match", "priority": "high"}],
        "conflicts_and_tradeoffs": ["Content denser than reference"],
    })
