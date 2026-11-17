'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import type { Analysis, Depth, Health, OutputKey, Project } from '../lib/api';
import { ApiError, OUTPUT_KEYS, api } from '../lib/api';
import { ConfigPanel } from './ConfigPanel';
import { Downloads } from './Downloads';
import { ProgressPanel } from './ProgressPanel';
import { Results } from './Results';
import { SlotState, UploadCard } from './UploadCard';

type Role = 'content' | 'design';
type Connection = { state: 'checking' } | { state: 'online'; health: Health } | { state: 'offline'; message: string };

const MAX_POLL_FAILURES = 5;

export function Studio({ pollMs = 2000, healthMs = 30000 }: { pollMs?: number; healthMs?: number }) {
  const [conn, setConn] = useState<Connection>({ state: 'checking' });
  const [slots, setSlots] = useState<Record<Role, SlotState>>({ content: { status: 'empty' }, design: { status: 'empty' } });
  const [depth, setDepth] = useState<Depth>('deep');
  const [outputs, setOutputs] = useState<OutputKey[]>([...OUTPUT_KEYS]);
  const [project, setProject] = useState<Project | null>(null);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pollWarning, setPollWarning] = useState<string | null>(null);
  const inspectSeq = useRef<Record<Role, number>>({ content: 0, design: 0 });

  // ---- backend health ----
  const checkHealth = useCallback(async () => {
    try {
      setConn({ state: 'online', health: await api.health() });
    } catch (e) {
      setConn({ state: 'offline', message: e instanceof Error ? e.message : 'Backend unreachable' });
    }
  }, []);
  useEffect(() => {
    checkHealth();
    const t = setInterval(checkHealth, healthMs);
    return () => clearInterval(t);
  }, [checkHealth, healthMs]);

  const maxMb = conn.state === 'online' ? conn.health.max_upload_mb : 50;
  const geminiReady = conn.state === 'online' && conn.health.gemini.configured;

  // ---- file selection + server-side inspection ----
  async function selectFile(role: Role, file: File) {
    const seq = ++inspectSeq.current[role];
    const set = (s: SlotState) => {
      if (inspectSeq.current[role] === seq) setSlots((prev) => ({ ...prev, [role]: s }));
    };
    const label = role === 'content' ? 'Content Authority' : 'Design Authority';
    if (!/\.pdf$/i.test(file.name) && file.type !== 'application/pdf') return set({ status: 'error', file: null, error: `${file.name} is not a PDF.` });
    if (file.size === 0) return set({ status: 'error', file: null, error: `${file.name} is empty.` });
    if (file.size > maxMb * 1024 * 1024) return set({ status: 'error', file: null, error: `${file.name} exceeds the ${maxMb} MB limit.` });
    set({ status: 'checking', file });
    try {
      set({ status: 'ready', file, info: await api.inspect(file) });
    } catch (e) {
      const msg = e instanceof Error ? e.message.replace(/^File\b/, label) : 'Could not validate the PDF.';
      set({ status: 'error', file, error: msg });
    }
  }

  function removeFile(role: Role) {
    inspectSeq.current[role]++;
    setSlots((prev) => ({ ...prev, [role]: { status: 'empty' } }));
  }

  // ---- start + poll ----
  const active = project?.status === 'queued' || project?.status === 'running';
  const locked = submitting || active;
  const content = slots.content;
  const design = slots.design;
  const canStart = content.status === 'ready' && design.status === 'ready' && outputs.length > 0 && !locked && geminiReady;

  async function start() {
    if (content.status !== 'ready' || design.status !== 'ready') return;
    setSubmitting(true);
    setError(null);
    setAnalysis(null);
    setProject(null);
    try {
      setProject(await api.createProject(content.file, design.file, depth, outputs));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not start the analysis.');
    } finally {
      setSubmitting(false);
    }
  }

  useEffect(() => {
    if (!project || !(project.status === 'queued' || project.status === 'running')) return;
    let cancelled = false;
    let failures = 0;
    let timer: ReturnType<typeof setTimeout>;
    const tick = async () => {
      try {
        const next = await api.project(project.id);
        if (cancelled) return;
        failures = 0;
        setPollWarning(null);
        setProject(next);
        if (next.status === 'queued' || next.status === 'running') timer = setTimeout(tick, pollMs);
      } catch (e) {
        if (cancelled) return;
        failures++;
        if (failures >= MAX_POLL_FAILURES) {
          setPollWarning(null);
          setError(`Lost contact with the backend while the analysis was running: ${e instanceof Error ? e.message : ''}`);
          return;
        }
        setPollWarning('Reconnecting to the backend…');
        timer = setTimeout(tick, pollMs * 2);
      }
    };
    timer = setTimeout(tick, pollMs);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
    // Only restart polling when a different project starts, or a project re-enters an active state.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project?.id, active, pollMs]);

  useEffect(() => {
    if (project?.status !== 'completed' || analysis) return;
    let cancelled = false;
    api
      .analysis(project.id)
      .then((a) => !cancelled && setAnalysis(a))
      .catch((e) => !cancelled && setError(e instanceof ApiError ? e.message : 'Could not load the analysis.'));
    return () => {
      cancelled = true;
    };
  }, [project?.status, project?.id, analysis]);

  function reset() {
    setProject(null);
    setAnalysis(null);
    setError(null);
    setSlots({ content: { status: 'empty' }, design: { status: 'empty' } });
  }

  // ---- render ----
  let startHint = '';
  if (conn.state === 'offline') startHint = 'Backend offline.';
  else if (conn.state === 'online' && !geminiReady)
    startHint = conn.health.gemini.api_key_present ? 'Set GEMINI_MODEL on the backend to enable analysis.' : 'Set GEMINI_API_KEY and GEMINI_MODEL on the backend to enable analysis.';
  else if (content.status !== 'ready' || design.status !== 'ready') startHint = 'Add both PDFs to continue.';
  else if (!outputs.length) startHint = 'Select at least one output.';

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand">
          <span className="mark" aria-hidden="true">
            <svg viewBox="0 0 24 24" width="18" height="18">
              <rect x="3" y="3" width="8" height="18" rx="1.5" fill="currentColor" opacity=".45" />
              <rect x="13" y="3" width="8" height="18" rx="1.5" fill="currentColor" />
            </svg>
          </span>
          <div>
            <div className="brand-name">Document Intelligence Studio</div>
            <div className="brand-sub">Gemini document analysis → Claude redesign Skill</div>
          </div>
        </div>
        <ConnectionBadge conn={conn} onRetry={checkHealth} />
      </header>

      <section className="intro">
        <h1>Analyse two PDFs. Get a Claude Skill that redesigns one in the style of the other.</h1>
        <p>
          Gemini reads the original files to learn what must be preserved in the content document, and the visual language of the design reference. It then packages
          a redesign plan as a Claude Skill.
        </p>
      </section>

      <div className="upload-grid">
        <UploadCard
          index="01"
          role="Content Authority"
          title="Content document"
          description="The source document whose content must remain intact: text, data, tables, terminology and structure."
          slot={content}
          disabled={locked}
          onSelect={(f) => selectFile('content', f)}
          onRemove={() => removeFile('content')}
        />
        <UploadCard
          index="02"
          role="Design Authority"
          title="Design reference"
          description="The visual reference that defines the redesign language. Its text is never copied."
          slot={design}
          disabled={locked}
          onSelect={(f) => selectFile('design', f)}
          onRemove={() => removeFile('design')}
        />
      </div>

      <ConfigPanel depth={depth} outputs={outputs} disabled={locked} onDepth={setDepth} onOutputs={setOutputs} />

      <div className="action-bar">
        <button type="button" className="btn-primary" disabled={!canStart} onClick={start}>
          {submitting ? 'Uploading…' : active ? 'Analysis running…' : 'Start analysis'}
        </button>
        <span className="muted">{startHint || `PDF only · up to ${maxMb} MB each`}</span>
        {project && !active && (
          <button type="button" className="btn-ghost" onClick={reset}>
            New analysis
          </button>
        )}
      </div>

      {error && (
        <div className="alert" role="alert">
          <b>Error</b>
          <span>{error}</span>
        </div>
      )}
      {pollWarning && <p className="hint">{pollWarning}</p>}

      {project && <ProgressPanel project={project} />}
      {project?.status === 'completed' && <Downloads project={project} />}
      {project?.status === 'completed' && !analysis && !error && <p className="hint">Loading results…</p>}
      {analysis && <Results analysis={analysis} />}

      <footer className="footer muted">Content authority ≠ design authority · Analysis by Google Gemini · Redesign executed by Claude</footer>
    </div>
  );
}

function ConnectionBadge({ conn, onRetry }: { conn: Connection; onRetry: () => void }) {
  if (conn.state === 'checking') return <span className="badge">Connecting…</span>;
  if (conn.state === 'offline')
    return (
      <button type="button" className="badge bad" onClick={onRetry} title={conn.message}>
        Backend offline · retry
      </button>
    );
  const g = conn.health.gemini;
  return (
    <span className={`badge ${g.configured ? 'good' : 'warn'}`} title={g.model ?? undefined}>
      {g.configured ? `Connected · ${g.model}` : 'Connected · Gemini not configured'}
    </span>
  );
}
