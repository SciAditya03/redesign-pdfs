'use client';

import { useEffect, useState } from 'react';
import type { Project } from '../lib/api';
import { formatDuration } from '../lib/format';

export function ProgressPanel({ project }: { project: Project }) {
  const active = project.status === 'queued' || project.status === 'running';
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!active) return;
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [active]);

  const start = project.started_at ? Date.parse(project.started_at) : null;
  const end = project.completed_at ? Date.parse(project.completed_at) : now;
  const elapsed = start ? formatDuration(end - start) : null;
  const done = project.stages.filter((s) => s.status === 'done').length;

  return (
    <section className="panel progress" aria-label="Analysis progress">
      <div className="progress-head">
        <h3 className="panel-title">
          {project.status === 'queued' && 'Queued'}
          {project.status === 'running' && 'Analysing'}
          {project.status === 'completed' && 'Analysis complete'}
          {project.status === 'failed' && 'Analysis failed'}
        </h3>
        <span className="muted mono">
          {done}/{project.stages.length} stages{elapsed ? ` · ${elapsed}` : ''} · {project.depth}
        </span>
      </div>
      <ol className="stages">
        {project.stages.map((s) => (
          <li key={s.key} className={`stage ${s.status}`} aria-current={s.status === 'running' ? 'step' : undefined}>
            <span className="stage-dot" aria-hidden="true">
              {s.status === 'done' ? '✓' : s.status === 'failed' ? '!' : ''}
            </span>
            <span className="stage-label">{s.label}</span>
            <span className="stage-status">{s.status === 'running' ? 'in progress' : s.status === 'pending' ? '' : s.status}</span>
          </li>
        ))}
      </ol>
      {active && <p className="hint">Gemini is reading the original PDFs. Deep analysis of long documents can take several minutes. You can keep this tab open.</p>}
      {project.status === 'failed' && project.error && (
        <div className="alert" role="alert">
          <b>{errorTitle(project.error.kind)}</b>
          <span>{project.error.message}</span>
        </div>
      )}
    </section>
  );
}

function errorTitle(kind: string): string {
  switch (kind) {
    case 'quota':
      return 'Gemini rate limit or quota reached';
    case 'auth':
      return 'Gemini API key rejected';
    case 'model_not_found':
      return 'Gemini model not available';
    case 'timeout':
      return 'Gemini timed out';
    case 'truncated':
      return 'Analysis too long for the output limit';
    case 'invalid_output':
      return 'Gemini returned an invalid structure';
    case 'interrupted':
      return 'Analysis interrupted';
    case 'config':
      return 'Backend not configured';
    default:
      return 'Something went wrong';
  }
}
