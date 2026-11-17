'use client';

import type { OutputKey, Project } from '../lib/api';
import { OUTPUT_KEYS, absoluteUrl } from '../lib/api';
import { OUTPUT_LABELS } from './ConfigPanel';

const FILE_NAMES: Record<OutputKey, string> = {
  skill_zip: 'document-redesign-specialist.zip',
  skill_md: 'SKILL.md',
  analysis_json: 'analysis.json',
};

export function Downloads({ project }: { project: Project }) {
  const available = OUTPUT_KEYS.filter((k) => project.downloads[k]);
  return (
    <section className="panel downloads" aria-label="Downloads">
      <h3 className="panel-title">Downloads</h3>
      <div className="download-grid">
        {available.map((key) => {
          const path = project.downloads[key]!;
          const href = absoluteUrl(key === 'skill_md' ? `${path}?download=true` : path);
          return (
            <a key={key} className={`download ${key === 'skill_zip' ? 'primary' : ''}`} href={href} download={FILE_NAMES[key]}>
              <span className="dl-icon" aria-hidden="true">
                ↓
              </span>
              <span>
                <b>{OUTPUT_LABELS[key].title}</b>
                <small>{FILE_NAMES[key]}</small>
              </span>
            </a>
          );
        })}
      </div>
      {available.length === 0 && <p className="muted">No downloadable outputs were selected for this project.</p>}
      <p className="hint">
        Next step: upload the Skill ZIP to Claude together with both original PDFs and ask Claude to redesign the content document.
      </p>
    </section>
  );
}
