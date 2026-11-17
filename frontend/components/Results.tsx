'use client';

import { useState } from 'react';
import type { Analysis } from '../lib/api';
import { formatPages } from '../lib/format';

type Tab = 'content' | 'design' | 'strategy';

export function Results({ analysis }: { analysis: Analysis }) {
  const [tab, setTab] = useState<Tab>('content');
  const tabs: { key: Tab; label: string }[] = [
    { key: 'content', label: 'Content analysis' },
    { key: 'design', label: 'Design analysis' },
    { key: 'strategy', label: 'Comparative strategy' },
  ];
  return (
    <section className="panel results" aria-label="Analysis results">
      <div className="tabs" role="tablist">
        {tabs.map((t) => (
          <button key={t.key} role="tab" aria-selected={tab === t.key} className={tab === t.key ? 'on' : ''} onClick={() => setTab(t.key)}>
            {t.label}
          </button>
        ))}
        <span className="tabs-meta mono muted">
          {analysis.generation_metadata.model} · {analysis.project.depth}
        </span>
      </div>
      <div role="tabpanel">
        {tab === 'content' && <ContentTab a={analysis} />}
        {tab === 'design' && <DesignTab a={analysis} />}
        {tab === 'strategy' && <StrategyTab a={analysis} />}
      </div>
    </section>
  );
}

function Metric({ value, label }: { value: number | string; label: string }) {
  return (
    <div className="metric">
      <b>{value}</b>
      <span>{label}</span>
    </div>
  );
}

/** Renders list items or table rows with a "show all" toggle. `cols` = render inside a <tbody>; otherwise inside a <ul>/<ol>. */
function Expandable<T>({ items, limit = 8, render, empty, cols }: { items: T[]; limit?: number; render: (item: T, i: number) => React.ReactNode; empty: string; cols?: number }) {
  const [all, setAll] = useState(false);
  const wrap = (node: React.ReactNode, key: string) =>
    cols ? (
      <tr key={key} className="row-extra">
        <td colSpan={cols}>{node}</td>
      </tr>
    ) : (
      <li key={key} className="row-extra">
        {node}
      </li>
    );
  if (!items.length) return empty ? wrap(<span className="muted">{empty}</span>, 'empty') : null;
  const shown = all ? items : items.slice(0, limit);
  return (
    <>
      {shown.map(render)}
      {items.length > limit &&
        wrap(
          <button type="button" className="btn-ghost more" onClick={() => setAll(!all)}>
            {all ? 'Show fewer' : `Show all ${items.length}`}
          </button>,
          'more',
        )}
    </>
  );
}

function ContentTab({ a }: { a: Analysis }) {
  const c = a.content_analysis;
  const doc = a.project.documents.find((d) => d.role === 'content_authority');
  return (
    <div className="tab-body">
      <div className="lead">
        <h3>{c.document_metadata.title ?? doc?.filename ?? 'Untitled document'}</h3>
        <p className="muted">
          {doc?.filename} · {c.document_metadata.document_type} · {c.document_metadata.language}
        </p>
        <p>{c.document_metadata.purpose}</p>
      </div>
      <div className="metrics">
        <Metric value={c.document_metadata.page_count} label="Pages" />
        <Metric value={c.sections.length} label="Sections" />
        <Metric value={c.tables.length} label="Tables" />
        <Metric value={c.figures.length} label="Figures" />
        <Metric value={c.terminology.length} label="Terms" />
        <Metric value={c.preservation_risks.length} label="Preservation risks" />
      </div>

      <h4>Sections</h4>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Section</th>
              <th>Pages</th>
              <th>Content</th>
            </tr>
          </thead>
          <tbody>
            <Expandable
              items={c.sections}
              cols={3}
              limit={12}
              empty="No sections recorded."
              render={(s, i) => (
                <tr key={i}>
                  <td style={{ paddingLeft: `${(s.level - 1) * 16 + 10}px` }}>{s.name}</td>
                  <td className="mono">{formatPages(range(s.start_page, s.end_page))}</td>
                  <td className="muted">{s.content_types.join(', ')}</td>
                </tr>
              )}
            />
          </tbody>
        </table>
      </div>

      <h4>Content inventory</h4>
      <div className="chips">
        {Object.entries(countBy(c.content_inventory.map((x) => x.kind))).map(([k, n]) => (
          <span key={k} className="chip">
            {k.replace(/_/g, ' ')} <b>{n}</b>
          </span>
        ))}
        {!c.content_inventory.length && <span className="muted">None recorded.</span>}
      </div>

      <h4>Preservation risks</h4>
      <ul className="risk-list">
        <Expandable
          items={c.preservation_risks}
          empty="No preservation risks recorded."
          render={(r, i) => (
            <li key={i} className={`risk ${r.severity}`}>
              <span className="sev">{r.severity}</span>
              <span>
                <b>{r.area}</b>
                {r.page != null && <span className="muted"> · p. {r.page}</span>}: {r.risk}
                <small className="muted"> → {r.mitigation}</small>
              </span>
            </li>
          )}
        />
      </ul>

      {c.manual_verification.length > 0 && (
        <>
          <h4>Needs manual verification</h4>
          <ul className="plain">
            <Expandable
              items={c.manual_verification}
              empty=""
              render={(v, i) => (
                <li key={i}>
                  {v.page != null && <span className="mono muted">p. {v.page} </span>}
                  {v.item}: <span className="muted">{v.reason}</span>
                </li>
              )}
            />
          </ul>
        </>
      )}
    </div>
  );
}

function DesignTab({ a }: { a: Analysis }) {
  const d = a.design_analysis;
  const ty = d.typography;
  return (
    <div className="tab-body">
      <div className="lead">
        <p>{d.visual_identity.summary}</p>
        {d.visual_identity.mood.length > 0 && <p className="muted">{d.visual_identity.mood.join(' · ')}</p>}
      </div>

      <h4>Colour palette</h4>
      <div className="palette">
        {d.colour_palette.map((c, i) => (
          <div key={i} className="swatch-card">
            <div className="swatch" style={{ background: c.hex ?? 'transparent' }} data-empty={!c.hex}>
              {!c.hex && <span>n/a</span>}
            </div>
            <b>{c.name}</b>
            <span className="mono">
              {c.hex ?? 'not inferable'}
              {c.hex && c.is_estimate ? ' ≈' : ''}
            </span>
            <small className="muted">{c.role}</small>
          </div>
        ))}
        {!d.colour_palette.length && <p className="muted">No colours recorded.</p>}
      </div>
      {d.colour_palette.some((c) => c.is_estimate) && <p className="hint">≈ estimated from the rendered reference.</p>}

      <h4>Typography</h4>
      <div className="type-grid">
        <div>
          <small className="eyebrow">Headings</small>
          <p>{ty.heading_font_characteristics}</p>
        </div>
        <div>
          <small className="eyebrow">Body</small>
          <p>{ty.body_font_characteristics}</p>
        </div>
        <div>
          <small className="eyebrow">Labels and captions</small>
          <p>{ty.label_caption_characteristics}</p>
        </div>
      </div>
      <p className="muted">
        Possible matches: {ty.possible_font_matches.length ? ty.possible_font_matches.join(', ') : 'not identified'} ({ty.font_identification_confidence} confidence)
      </p>

      <h4>Page archetypes</h4>
      <div className="cards">
        {d.page_archetypes.map((p, i) => (
          <div key={i} className="mini-card">
            <div className="mini-head">
              <b>{p.label}</b>
              <span className="mono muted">p. {formatPages(p.pages)}</span>
            </div>
            <span className="chip">{p.archetype.replace(/_/g, ' ')}</span>
            <p>{p.layout_description}</p>
          </div>
        ))}
        {!d.page_archetypes.length && <p className="muted">No archetypes recorded.</p>}
      </div>

      <h4>Reusable components</h4>
      <ul className="plain">
        <Expandable
          items={d.components}
          empty="No components recorded."
          render={(c, i) => (
            <li key={i}>
              <b>{c.name}</b> <span className="chip">{c.category.replace(/_/g, ' ')}</span>
              <span className="muted"> {c.description}</span>
            </li>
          )}
        />
      </ul>

      <h4>Layout</h4>
      <p>
        {d.page_geometry.page_size}, {d.page_geometry.orientation}. {d.page_geometry.column_structure}. Margins: {d.page_geometry.margins}.
      </p>
      {d.uncertainties.length > 0 && (
        <>
          <h4>Uncertainties</h4>
          <ul className="plain muted">
            {d.uncertainties.map((u, i) => (
              <li key={i}>{u}</li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

function StrategyTab({ a }: { a: Analysis }) {
  const c = a.comparative_analysis;
  const arch = [...c.proposed_architecture].sort((x, y) => x.order - y.order);
  return (
    <div className="tab-body">
      <div className="lead">
        <p>{c.redesign_strategy.overview}</p>
      </div>

      <h4>Content → design mapping</h4>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Content</th>
              <th>Treatment</th>
              <th>Archetype</th>
              <th>Pages</th>
            </tr>
          </thead>
          <tbody>
            <Expandable
              items={c.content_to_design_mapping}
              cols={4}
              limit={10}
              empty="No mappings recorded."
              render={(m, i) => (
                <tr key={i}>
                  <td>{m.content_element}</td>
                  <td>{m.recommended_treatment}</td>
                  <td className="muted">{m.archetype.replace(/_/g, ' ')}</td>
                  <td className="mono">{formatPages(m.source_pages)}</td>
                </tr>
              )}
            />
          </tbody>
        </table>
      </div>

      <h4>Proposed document architecture</h4>
      <ol className="arch">
        <Expandable
          items={arch}
          limit={12}
          empty="No architecture proposed."
          render={(e) => (
            <li key={e.order}>
              <span className="arch-n mono">{String(e.order).padStart(2, '0')}</span>
              <span>
                <b>{e.page_role}</b> <span className="chip">{e.archetype.replace(/_/g, ' ')}</span>
                <span className="muted"> {e.content}</span>
              </span>
            </li>
          )}
        />
      </ol>

      <h4>Key redesign rules</h4>
      <div className="rules">
        <RuleGroup title="Typography" items={c.redesign_strategy.typography_rules} />
        <RuleGroup title="Colour" items={c.redesign_strategy.colour_rules} />
        <RuleGroup title="Spacing" items={c.redesign_strategy.spacing_rules} />
        <RuleGroup title="Tables" items={c.redesign_strategy.table_guidance} />
        <RuleGroup title="Content preservation" items={c.redesign_strategy.content_preservation_strategy} />
      </div>
      {c.conflicts_and_tradeoffs.length > 0 && (
        <>
          <h4>Conflicts and trade-offs</h4>
          <ul className="plain">
            {c.conflicts_and_tradeoffs.map((t, i) => (
              <li key={i}>{t}</li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

function RuleGroup({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null;
  return (
    <div className="rule-group">
      <small className="eyebrow">{title}</small>
      <ul className="plain">
        {items.slice(0, 5).map((r, i) => (
          <li key={i}>{r}</li>
        ))}
      </ul>
    </div>
  );
}

function range(a: number, b: number): number[] {
  const out: number[] = [];
  for (let i = a; i <= Math.max(a, b); i++) out.push(i);
  return out;
}

function countBy(xs: string[]): Record<string, number> {
  return xs.reduce<Record<string, number>>((acc, x) => ((acc[x] = (acc[x] ?? 0) + 1), acc), {});
}
