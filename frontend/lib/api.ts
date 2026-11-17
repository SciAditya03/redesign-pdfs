// Typed client for the Document Intelligence Studio backend.
// The browser only talks to our backend; the Gemini API key never leaves the server.

export const API_URL = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/$/, '');

export type Depth = 'standard' | 'deep';
export type OutputKey = 'skill_zip' | 'skill_md' | 'analysis_json';
export const OUTPUT_KEYS: OutputKey[] = ['skill_zip', 'skill_md', 'analysis_json'];

export type Health = {
  status: string;
  gemini: { configured: boolean; api_key_present: boolean; model: string | null };
  max_upload_mb: number;
};

export type PdfInfo = {
  filename: string;
  page_count: number;
  size_bytes: number;
  width_pt: number;
  height_pt: number;
  text_chars: number;
  likely_scanned: boolean;
  title: string | null;
};

export type StageStatus = 'pending' | 'running' | 'done' | 'failed';
export type Stage = { key: string; label: string; status: StageStatus };
export type ProjectStatus = 'queued' | 'running' | 'completed' | 'failed';

export type Project = {
  id: string;
  status: ProjectStatus;
  depth: Depth;
  outputs: OutputKey[];
  created_at: string;
  updated_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  current_stage: string | null;
  stages: Stage[];
  documents: { content: PdfInfo; design: PdfInfo };
  error: { kind: string; message: string } | null;
  summary: Record<string, Record<string, number | string | null>> | null;
  downloads: Partial<Record<OutputKey, string>>;
};

// ---- analysis (mirrors backend/app/schemas/analysis.py) ----
type Conf = 'high' | 'medium' | 'low';
export type Evidence = { page: number | null; observation: string; basis: 'observed' | 'inferred'; confidence: Conf; notes: string | null };

export type ContentAnalysis = {
  document_metadata: { title: string | null; document_type: string; purpose: string; language: string; page_count: number; executive_summary: string };
  sections: { name: string; level: number; parent: string | null; start_page: number; end_page: number; content_types: string[]; approx_word_count: number | null; structural_notes: string | null; preservation_risks: string[] }[];
  page_inventory: { page: number; summary: string; content_types: string[]; density: 'low' | 'medium' | 'high'; has_tables: boolean; has_figures: boolean; small_or_hard_to_read_text: boolean; appears_scanned: boolean; notes: string | null }[];
  content_inventory: { kind: string; page: number; label: string; detail: string | null }[];
  tables: { id: string; page: number; title: string | null; columns: string[]; row_count: number | null; notes: string | null; extraction_confidence: Conf }[];
  figures: { id: string; page: number; kind: string; caption: string | null; description: string }[];
  numerical_data: { page: number; value: string; context: string }[];
  terminology: { term: string; category: string; pages: number[]; notes: string | null }[];
  references: { page: number; kind: string; excerpt: string }[];
  repeated_information: string[];
  preservation_risks: { page: number | null; area: string; risk: string; severity: Conf; mitigation: string }[];
  manual_verification: { page: number | null; item: string; reason: string }[];
  evidence: Evidence[];
};

export type DesignAnalysis = {
  visual_identity: { summary: string; mood: string[]; brand_elements: string[]; contrast_notes: string };
  colour_palette: { name: string; hex: string | null; role: string; usage: string; is_estimate: boolean; pages: number[] }[];
  typography: {
    heading_font_characteristics: string; body_font_characteristics: string; label_caption_characteristics: string;
    possible_font_matches: string[]; font_identification_confidence: Conf;
    hierarchy: { level: string; usage: string; font_characteristics: string; relative_size: string; weight: string; case: string; letter_spacing: string; line_spacing: string; colour_role: string | null }[];
    alignment: string; notes: string | null;
  };
  page_geometry: { page_size: string; width_mm: number | null; height_mm: number | null; orientation: string; margins: string; column_structure: string; grid_system: string; content_width: string; header_height: string | null; footer_height: string | null; whitespace: string };
  components: { name: string; category: string; description: string; visual_spec: string; usage_rules: string; pages: number[] }[];
  page_archetypes: { archetype: string; label: string; pages: number[]; layout_description: string; key_components: string[]; content_capacity: string }[];
  page_inventory: { page: number; archetype: string; notes: string | null }[];
  image_guidelines: string[];
  evidence: Evidence[];
  uncertainties: string[];
};

export type ComparativeAnalysis = {
  content_to_design_mapping: { content_element: string; source_pages: number[]; recommended_treatment: string; archetype: string; component: string | null; rationale: string }[];
  redesign_strategy: {
    overview: string; typography_rules: string[]; colour_rules: string[]; spacing_rules: string[]; image_guidance: string[];
    table_guidance: string[]; header_footer_rules: string[]; component_system: string[]; content_preservation_strategy: string[]; quality_control_strategy: string[];
  };
  proposed_architecture: { order: number; page_role: string; archetype: string; content: string; source_pages: number[]; notes: string | null }[];
  quality_requirements: { check: string; description: string; priority: Conf }[];
  conflicts_and_tradeoffs: string[];
};

export type Analysis = {
  project: { id: string; depth: Depth; created_at: string; documents: { role: string; filename: string; page_count: number; size_bytes: number }[] };
  content_analysis: ContentAnalysis;
  design_analysis: DesignAnalysis;
  comparative_analysis: ComparativeAnalysis;
  generation_metadata: { provider: string; model: string; sdk: string; schema_version: string; started_at: string; completed_at: string; stages: { stage: string; attempts: number; duration_seconds: number }[] };
};

// ---- requests ----
export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, init);
  } catch {
    throw new ApiError(`Cannot reach the backend at ${API_URL}. Is it running, and is this site listed in CORS_ORIGINS?`, 0);
  }
  if (!res.ok) {
    let message = `Request failed (HTTP ${res.status}).`;
    try {
      const body = await res.json();
      if (typeof body?.detail === 'string') message = body.detail;
      else if (Array.isArray(body?.detail)) message = body.detail.map((d: { msg?: string }) => d.msg).join('; ');
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(message, res.status);
  }
  return (await res.json()) as T;
}

export const api = {
  health: () => request<Health>('/api/health'),
  inspect: (file: File) => {
    const fd = new FormData();
    fd.append('file', file);
    return request<PdfInfo>('/api/documents/inspect', { method: 'POST', body: fd });
  },
  createProject: (content: File, design: File, depth: Depth, outputs: OutputKey[]) => {
    const fd = new FormData();
    fd.append('content_pdf', content);
    fd.append('design_pdf', design);
    fd.append('depth', depth);
    fd.append('outputs', outputs.join(','));
    return request<Project>('/api/projects', { method: 'POST', body: fd });
  },
  project: (id: string) => request<Project>(`/api/projects/${encodeURIComponent(id)}`),
  analysis: (id: string) => request<Analysis>(`/api/projects/${encodeURIComponent(id)}/analysis`),
};

export function absoluteUrl(path: string): string {
  return `${API_URL}${path}`;
}
