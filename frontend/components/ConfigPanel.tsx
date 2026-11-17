'use client';

import type { Depth, OutputKey } from '../lib/api';
import { OUTPUT_KEYS } from '../lib/api';

export const OUTPUT_LABELS: Record<OutputKey, { title: string; sub: string }> = {
  skill_zip: { title: 'Complete Claude Skill ZIP', sub: 'SKILL.md, supporting guides and analysis.json' },
  skill_md: { title: 'Standalone SKILL.md', sub: 'The main instruction file only' },
  analysis_json: { title: 'Structured analysis JSON', sub: 'The full validated Gemini analysis' },
};

type Props = {
  depth: Depth;
  outputs: OutputKey[];
  disabled?: boolean;
  onDepth: (d: Depth) => void;
  onOutputs: (o: OutputKey[]) => void;
};

export function ConfigPanel({ depth, outputs, disabled, onDepth, onOutputs }: Props) {
  function toggle(key: OutputKey) {
    onOutputs(outputs.includes(key) ? outputs.filter((k) => k !== key) : OUTPUT_KEYS.filter((k) => k === key || outputs.includes(k)));
  }
  return (
    <section className="panel config" aria-label="Analysis configuration">
      <div className="config-col">
        <h3 className="panel-title">Analysis depth</h3>
        <div className="segmented" role="radiogroup" aria-label="Analysis depth">
          {(['standard', 'deep'] as Depth[]).map((d) => (
            <button
              key={d}
              type="button"
              role="radio"
              aria-checked={depth === d}
              className={depth === d ? 'on' : ''}
              disabled={disabled}
              onClick={() => onDepth(d)}
            >
              {d === 'deep' ? 'Deep' : 'Standard'}
            </button>
          ))}
        </div>
        <p className="hint">
          {depth === 'deep'
            ? 'Document-wide and page-by-page: every page inventoried, with page-cited evidence. Slower.'
            : 'Document-level analysis plus representative pages. Faster.'}
        </p>
      </div>
      <div className="config-col">
        <h3 className="panel-title">Outputs</h3>
        <div className="checks">
          {OUTPUT_KEYS.map((key) => (
            <label key={key} className={`check ${outputs.includes(key) ? 'on' : ''}`}>
              <input type="checkbox" checked={outputs.includes(key)} disabled={disabled} onChange={() => toggle(key)} />
              <span>
                <b>{OUTPUT_LABELS[key].title}</b>
                <small>{OUTPUT_LABELS[key].sub}</small>
              </span>
            </label>
          ))}
        </div>
        {outputs.length === 0 && <p className="hint err">Select at least one output.</p>}
      </div>
    </section>
  );
}
