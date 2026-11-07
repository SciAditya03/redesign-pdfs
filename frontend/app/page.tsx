'use client';
import { useState } from 'react';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

type Result = {
  id: string;
  original: { filename: string; pages: number; text_chars: number; likely_scanned: boolean };
  reference: { filename: string; pages: number };
  content_blocks: number;
  qwen_enabled: boolean;
  design: any;
};

export default function Home() {
  const [original, setOriginal] = useState<File | null>(null);
  const [reference, setReference] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<Result | null>(null);
  const [design, setDesign] = useState<any>(null);
  const [saved, setSaved] = useState(false);
  const [generated, setGenerated] = useState<any>(null);

  async function analyse() {
    if (!original || !reference) return;
    setBusy(true);
    setError('');
    setResult(null);
    setDesign(null);
    setSaved(false);
    setGenerated(null);
    try {
      const fd = new FormData();
      fd.append('original', original);
      fd.append('reference', reference);
      const r = await fetch(`${API}/api/projects`, { method: 'POST', body: fd });
      if (!r.ok) throw new Error(await r.text());
      const data = await r.json();
      setResult(data);
      setDesign(data.design);
    } catch (e: any) {
      setError(
        e instanceof TypeError
          ? `Cannot reach the backend at ${API}. Start FastAPI on port 8000, check frontend/.env.local, and confirm CORS_ORIGINS includes this website. Details: ${e.message}`
          : e.message || 'Could not analyse files'
      );
    } finally {
      setBusy(false);
    }
  }

  async function saveDesign() {
    if (!result || !design) return;
    setBusy(true);
    setError('');
    try {
      const r = await fetch(`${API}/api/projects/${result.id}/design`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(design)
      });
      if (!r.ok) throw new Error(await r.text());
      setSaved(true);
    } catch (e: any) {
      setError(e.message || 'Could not save design');
    } finally {
      setBusy(false);
    }
  }

  async function generate() {
    if (!result) return;
    if (!saved) {
      await saveDesign();
    }
    setBusy(true);
    setError('');
    try {
      const r = await fetch(`${API}/api/projects/${result.id}/generate`, { method: 'POST' });
      if (!r.ok) throw new Error(await r.text());
      setGenerated(await r.json());
    } catch (e: any) {
      setError(e.message || 'Generation failed');
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="shell">
      <header className="top">
        <div className="brand">
          <div className="mark">R</div>
          <div>
            RE:DESIGN AI<div className="tag">DOCUMENT INTELLIGENCE STUDIO</div>
          </div>
        </div>
        <span className="tag">MVP · 0.1.0</span>
      </header>

      <section className="hero">
        <div className="tag">REFERENCE-GUIDED DOCUMENT GENERATION</div>
        <h1>
          Transform documents.<br />
          <span style={{ color: 'var(--green)' }}>Preserve their meaning.</span>
        </h1>
        <p>
          Upload the document you want to redesign and a visual reference. Qwen analyses the reference while the
          renderer preserves your source content and produces an editable presentation alongside a print-ready PDF.
        </p>
      </section>

      <section className="grid">
        <div className="upload">
          <div>
            <div className="tag">01 / CONTENT AUTHORITY</div>
            <h3>Original document</h3>
            <p>The source of truth for all wording, data and terminology.</p>
          </div>
          <div className="drop">
            <input type="file" accept="application/pdf" onChange={e => setOriginal(e.target.files?.[0] || null)} />
            <div className="status">{original ? `Selected: ${original.name}` : 'Choose original PDF'}</div>
          </div>
        </div>

        <div className="upload">
          <div>
            <div className="tag">02 / DESIGN AUTHORITY</div>
            <h3>Visual reference</h3>
            <p>We learn its colours, typography, spacing and page structures — not its content.</p>
          </div>
          <div className="drop">
            <input type="file" accept="application/pdf" onChange={e => setReference(e.target.files?.[0] || null)} />
            <div className="status">{reference ? `Selected: ${reference.name}` : 'Choose reference PDF'}</div>
          </div>
        </div>
      </section>

      <div className="actions">
        <button className="btn" disabled={!original || !reference || busy} onClick={analyse}>
          {busy ? 'Working…' : 'Analyse both documents →'}
        </button>
        <span className="status">PDF · max 80 MB each · A4-first rendering</span>
      </div>
      {error && (
        <div className="panel" style={{ color: '#b42318' }}>
          {error}
        </div>
      )}

      {result && (
        <>
          <section className="panel">
            <div className="tag">ANALYSIS COMPLETE · PROJECT {result.id.slice(0, 8)}</div>
            <h2 style={{ color: 'var(--navy)' }}>What the system found</h2>
            <div className="grid">
              <div className="metric">
                <b>{result.original.pages}</b>
                <span>Original pages</span>
              </div>
              <div className="metric">
                <b>{result.reference.pages}</b>
                <span>Reference pages</span>
              </div>
              <div className="metric">
                <b>{result.content_blocks}</b>
                <span>Extracted content blocks</span>
              </div>
              <div className="metric">
                <b>{result.qwen_enabled ? 'Qwen API' : 'Fallback'}</b>
                <span>Visual analysis mode</span>
              </div>
            </div>

            <h3>Review and edit design system</h3>
            <div className="grid">
              <label className="status">
                Primary colour
                <input
                  className="field"
                  type="color"
                  value={design?.tokens?.primary_color || '#191F5B'}
                  onChange={e => {
                    setDesign({ ...design, tokens: { ...design.tokens, primary_color: e.target.value } });
                    setSaved(false);
                  }}
                />
              </label>
              <label className="status">
                Accent colour
                <input
                  className="field"
                  type="color"
                  value={design?.tokens?.accent_color || '#079B4B'}
                  onChange={e => {
                    setDesign({ ...design, tokens: { ...design.tokens, accent_color: e.target.value } });
                    setSaved(false);
                  }}
                />
              </label>
              <label className="status">
                Heading font
                <input
                  className="field"
                  value={design?.tokens?.heading_font || 'Poppins'}
                  onChange={e => {
                    setDesign({ ...design, tokens: { ...design.tokens, heading_font: e.target.value } });
                    setSaved(false);
                  }}
                />
              </label>
              <label className="status">
                Body font
                <input
                  className="field"
                  value={design?.tokens?.body_font || 'Inter'}
                  onChange={e => {
                    setDesign({ ...design, tokens: { ...design.tokens, body_font: e.target.value } });
                    setSaved(false);
                  }}
                />
              </label>
            </div>

            <div className="swatches">
              {[
                design?.tokens?.primary_color || '#191F5B',
                design?.tokens?.accent_color || '#079B4B',
                design?.tokens?.surface_color || '#FFFFFF',
                design?.tokens?.background_color || '#F9FAFB'
              ].map((c: string) => (
                <div key={c} className="swatch" title={c} style={{ background: c }} />
              ))}
            </div>

            <div className="row">
              <span className="tag">HEADING: {design?.tokens?.heading_font || 'Poppins'}</span>
              <span className="tag">BODY: {design?.tokens?.body_font || 'Inter'}</span>
              <span className="tag">PAGE: {design?.tokens?.page_size || 'A4'}</span>
            </div>

            {result.original.likely_scanned && (
              <p style={{ color: '#a15c00' }}>
                Warning: the original appears image-based or has little extractable text. OCR is required for reliable
                preservation.
              </p>
            )}

            <p className="status">
              Design observations: {design?.observations ? design.observations.join(' · ') : 'No observations returned.'}
            </p>

            <div className="row">
              <button className="btn" disabled={busy} onClick={saveDesign}>
                {busy ? 'Saving…' : 'Save design changes'}
              </button>
              <button className="btn" disabled={busy} onClick={generate}>
                {busy ? 'Generating…' : 'Generate PDF + editable PPTX →'}
              </button>
            </div>
          </section>
        </>
      )}

      {generated && (
        <section className="panel">
          <div className="tag">EXPORTS READY</div>
          <h2 style={{ color: 'var(--navy)' }}>Your redesigned documents</h2>
          <div className="row">
            <a className="link" href={`${API}${generated.pdf_url}`}>
              ↓ Download PDF
            </a>
