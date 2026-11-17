import type { Analysis, Health, PdfInfo, Project } from '../lib/api';

export const health: Health = { status: 'ok', gemini: { configured: true, api_key_present: true, model: 'gemini-test' }, max_upload_mb: 50 };

export function pdfInfo(filename: string, pages: number): PdfInfo {
  return { filename, page_count: pages, size_bytes: 1234, width_pt: 595, height_pt: 842, text_chars: 5000, likely_scanned: false, title: null };
}

const STAGES = [
  ['validating', 'Validating documents'],
  ['preparing', 'Preparing PDFs'],
  ['content', 'Analysing content authority'],
  ['design', 'Analysing design authority'],
  ['comparative', 'Performing comparative analysis'],
  ['skill', 'Generating Claude Skill'],
  ['downloads', 'Preparing downloads'],
] as const;

export function project(status: Project['status'], doneCount: number, extra: Partial<Project> = {}): Project {
  return {
    id: 'abc123abc123abc123abc123abc123ab',
    status,
    depth: 'deep',
    outputs: ['skill_zip', 'skill_md', 'analysis_json'],
    created_at: '2026-11-18T10:00:00+00:00',
    updated_at: null,
    started_at: '2026-11-18T10:00:01+00:00',
    completed_at: status === 'completed' || status === 'failed' ? '2026-11-18T10:02:01+00:00' : null,
    current_stage: null,
    stages: STAGES.map(([key, label], i) => ({
      key,
      label,
      status: i < doneCount ? 'done' : i === doneCount && status === 'running' ? 'running' : i === doneCount && status === 'failed' ? 'failed' : 'pending',
    })),
    documents: { content: pdfInfo('content.pdf', 12), design: pdfInfo('design.pdf', 8) },
    error: null,
    summary: null,
    downloads:
      status === 'completed'
        ? { skill_zip: '/api/projects/abc/download/skill', skill_md: '/api/projects/abc/skill', analysis_json: '/api/projects/abc/download/analysis' }
        : {},
    ...extra,
  };
}

export const analysis: Analysis = {
  project: {
    id: 'abc',
    depth: 'deep',
    created_at: '',
    documents: [
      { role: 'content_authority', filename: 'content.pdf', page_count: 12, size_bytes: 1 },
      { role: 'design_authority', filename: 'design.pdf', page_count: 8, size_bytes: 1 },
    ],
  },
  content_analysis: {
    document_metadata: { title: 'Assay Capabilities Catalogue', document_type: 'catalogue', purpose: 'Lists assays', language: 'en', page_count: 12, executive_summary: '' },
    sections: [{ name: 'Proteomics', level: 1, parent: null, start_page: 3, end_page: 5, content_types: ['table'], approx_word_count: 300, structural_notes: null, preservation_risks: [] }],
    page_inventory: [],
    content_inventory: [{ kind: 'table', page: 3, label: 'T1', detail: null }],
    tables: [],
    figures: [],
    numerical_data: [],
    terminology: [],
    references: [],
    repeated_information: [],
    preservation_risks: [{ page: 4, area: 'LOD table', risk: 'Tiny superscripts', severity: 'high', mitigation: 'Verify manually' }],
    manual_verification: [],
    evidence: [],
  },
  design_analysis: {
    visual_identity: { summary: 'Calm navy scientific identity', mood: ['precise'], brand_elements: [], contrast_notes: '' },
    colour_palette: [
      { name: 'Navy', hex: '#191F5B', role: 'primary', usage: 'Headings', is_estimate: true, pages: [1] },
      { name: 'Tint', hex: null, role: 'other', usage: 'Overlay', is_estimate: true, pages: [2] },
    ],
    typography: {
      heading_font_characteristics: 'Geometric sans',
      body_font_characteristics: 'Humanist sans',
      label_caption_characteristics: 'Mono caps',
      possible_font_matches: ['Manrope'],
      font_identification_confidence: 'low',
      hierarchy: [],
      alignment: 'left',
      notes: null,
    },
    page_geometry: { page_size: 'A4', width_mm: 210, height_mm: 297, orientation: 'portrait', margins: '18 mm', column_structure: 'Two columns', grid_system: '', content_width: '', header_height: null, footer_height: null, whitespace: '' },
    components: [{ name: 'Section band', category: 'section_opener', description: 'Full-bleed band', visual_spec: '', usage_rules: '', pages: [2] }],
    page_archetypes: [{ archetype: 'cover', label: 'Hero cover', pages: [1], layout_description: 'Full-bleed photo', key_components: [], content_capacity: '' }],
    page_inventory: [],
    image_guidelines: [],
    evidence: [],
    uncertainties: [],
  },
  comparative_analysis: {
    content_to_design_mapping: [{ content_element: 'Main section', source_pages: [3, 4, 5], recommended_treatment: 'Section opener band', archetype: 'section_opener', component: null, rationale: '' }],
    redesign_strategy: {
      overview: 'Apply the navy system with generous whitespace.',
      typography_rules: ['H1 bold geometric'],
      colour_rules: [],
      spacing_rules: [],
      image_guidance: [],
      table_guidance: [],
      header_footer_rules: [],
      component_system: [],
      content_preservation_strategy: [],
      quality_control_strategy: [],
    },
    proposed_architecture: [
      { order: 2, page_role: 'Contents', archetype: 'contents', content: 'All sections', source_pages: [2], notes: null },
      { order: 1, page_role: 'Cover', archetype: 'cover', content: 'Title', source_pages: [1], notes: null },
    ],
    quality_requirements: [],
    conflicts_and_tradeoffs: [],
  },
  generation_metadata: { provider: 'google-gemini', model: 'gemini-test', sdk: 'google-genai', schema_version: '1.0', started_at: '', completed_at: '', stages: [] },
};
