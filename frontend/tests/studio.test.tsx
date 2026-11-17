import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { Studio } from '../components/Studio';
import { analysis, health, pdfInfo, project } from './fixtures';

type Handler = (init: RequestInit | undefined) => { status?: number; body: unknown };

let routes: Record<string, Handler | Handler[]>;
let calls: { key: string; init?: RequestInit }[];

function json(status: number, body: unknown) {
  return Promise.resolve(new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }));
}

beforeEach(() => {
  calls = [];
  routes = {
    'GET /api/health': () => ({ body: health }),
    'POST /api/documents/inspect': (init) => {
      const f = (init!.body as FormData).get('file') as File;
      if (f.name.startsWith('bad')) return { status: 400, body: { detail: 'File could not be opened as a PDF: it may be corrupt.' } };
      return { body: pdfInfo(f.name, f.name.includes('design') ? 8 : 12) };
    },
  };
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string, init?: RequestInit) => {
      const path = new URL(url).pathname;
      const key = `${init?.method ?? 'GET'} ${path}`;
      calls.push({ key, init });
      const route = routes[key];
      if (!route) return json(404, { detail: `no mock for ${key}` });
      const handler = Array.isArray(route) ? (route.length > 1 ? route.shift()! : route[0]) : route;
      const { status = 200, body } = handler(init);
      return json(status, body);
    }),
  );
});

const pdf = (name: string, size = 2048) => new File([new Uint8Array(size)], name, { type: 'application/pdf' });

async function addBoth(user: ReturnType<typeof userEvent.setup>) {
  await user.upload(screen.getByLabelText('Content Authority PDF'), pdf('content.pdf'));
  await user.upload(screen.getByLabelText('Design Authority PDF'), pdf('design.pdf'));
  await screen.findByText('12 pages', { exact: false });
  await screen.findByText('8 pages', { exact: false });
}

describe('Studio', () => {
  it('shows both upload areas, backend status, and a disabled start button', async () => {
    render(<Studio pollMs={5} />);
    expect(screen.getByText('01 — Content Authority')).toBeInTheDocument();
    expect(screen.getByText('02 — Design Authority')).toBeInTheDocument();
    expect(await screen.findByText('Connected · gemini-test')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Start analysis' })).toBeDisabled();
    expect(screen.getByText('Add both PDFs to continue.')).toBeInTheDocument();
  });

  it('validates uploads, then enables start once both are valid', async () => {
    const user = userEvent.setup();
    render(<Studio pollMs={5} />);
    await screen.findByText('Connected · gemini-test');
    await user.upload(screen.getByLabelText('Content Authority PDF'), pdf('content.pdf'));
    expect(await screen.findByText('content.pdf')).toBeInTheDocument();
    expect(await screen.findByText(/12 pages/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Start analysis' })).toBeDisabled();
    await user.upload(screen.getByLabelText('Design Authority PDF'), pdf('design.pdf'));
    await screen.findByText(/8 pages/);
    expect(screen.getByRole('button', { name: 'Start analysis' })).toBeEnabled();
  });

  it('shows server-side validation errors and rejects non-PDF and empty files locally', async () => {
    const user = userEvent.setup({ applyAccept: false });
    render(<Studio pollMs={5} />);
    await screen.findByText('Connected · gemini-test');
    const input = screen.getByLabelText('Content Authority PDF');
    await user.upload(input, pdf('bad.pdf'));
    expect(await screen.findByText('Content Authority could not be opened as a PDF: it may be corrupt.')).toBeInTheDocument();
    await user.upload(input, new File(['hi'], 'notes.txt', { type: 'text/plain' }));
    expect(await screen.findByText('notes.txt is not a PDF.')).toBeInTheDocument();
    await user.upload(input, pdf('empty.pdf', 0));
    expect(await screen.findByText('empty.pdf is empty.')).toBeInTheDocument();
    expect(calls.filter((c) => c.key === 'POST /api/documents/inspect')).toHaveLength(1);
    expect(screen.getByRole('button', { name: 'Start analysis' })).toBeDisabled();
  });

  it('replaces and removes a selected file', async () => {
    const user = userEvent.setup();
    render(<Studio pollMs={5} />);
    await screen.findByText('Connected · gemini-test');
    const input = screen.getByLabelText('Content Authority PDF');
    await user.upload(input, pdf('content.pdf'));
    await screen.findByText('content.pdf');
    await user.upload(input, pdf('content-v2.pdf'));
    expect(await screen.findByText('content-v2.pdf')).toBeInTheDocument();
    expect(screen.queryByText('content.pdf')).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Remove Content Authority PDF' }));
    expect(screen.queryByText('content-v2.pdf')).not.toBeInTheDocument();
    expect(screen.getAllByText('Drop a PDF here')).toHaveLength(2);
  });

  it('disables start when Gemini is not configured on the backend', async () => {
    routes['GET /api/health'] = () => ({ body: { ...health, gemini: { configured: false, api_key_present: false, model: null } } });
    const user = userEvent.setup();
    render(<Studio pollMs={5} />);
    expect(await screen.findByText('Connected · Gemini not configured')).toBeInTheDocument();
    await addBoth(user);
    expect(screen.getByRole('button', { name: 'Start analysis' })).toBeDisabled();
    expect(screen.getByText('Set GEMINI_API_KEY and GEMINI_MODEL on the backend to enable analysis.')).toBeInTheDocument();
  });

  it('shows backend offline', async () => {
    routes = {};
    vi.mocked(fetch).mockImplementation(() => Promise.reject(new TypeError('Failed to fetch')));
    render(<Studio pollMs={5} />);
    expect(await screen.findByRole('button', { name: 'Backend offline · retry' })).toBeInTheDocument();
  });

  it('runs an analysis: sends both files and settings, shows real stage progress, results and downloads', async () => {
    routes['POST /api/projects'] = () => ({ status: 202, body: project('queued', 1) });
    routes['GET /api/projects/abc123abc123abc123abc123abc123ab'] = [
      () => ({ body: project('running', 2) }),
      () => ({ body: project('running', 4) }),
      () => ({ body: project('completed', 7) }),
    ];
    routes['GET /api/projects/abc123abc123abc123abc123abc123ab/analysis'] = () => ({ body: analysis });

    const user = userEvent.setup();
    render(<Studio pollMs={5} />);
    await screen.findByText('Connected · gemini-test');
    await addBoth(user);
    await user.click(screen.getByRole('radio', { name: 'Standard' }));
    await user.click(screen.getByLabelText(/Standalone SKILL.md/));
    await user.click(screen.getByRole('button', { name: 'Start analysis' }));

    const post = calls.find((c) => c.key === 'POST /api/projects')!;
    const fd = post.init!.body as FormData;
    expect((fd.get('content_pdf') as File).name).toBe('content.pdf');
    expect((fd.get('design_pdf') as File).name).toBe('design.pdf');
    expect(fd.get('depth')).toBe('standard');
    expect(fd.get('outputs')).toBe('skill_zip,analysis_json');

    expect(await screen.findByText('Analysis complete')).toBeInTheDocument();
    const progress = screen.getByRole('region', { name: 'Analysis progress' });
    expect(within(progress).getByText('7/7 stages', { exact: false })).toBeInTheDocument();

    const downloads = screen.getByRole('region', { name: 'Downloads' });
    expect(within(downloads).getByRole('link', { name: /Complete Claude Skill ZIP/ })).toHaveAttribute('href', 'http://localhost:8000/api/projects/abc/download/skill');
    expect(within(downloads).getByRole('link', { name: /Standalone SKILL.md/ })).toHaveAttribute('href', 'http://localhost:8000/api/projects/abc/skill?download=true');
    expect(within(downloads).getByRole('link', { name: /Structured analysis JSON/ })).toHaveAttribute('href', 'http://localhost:8000/api/projects/abc/download/analysis');

    // Results dashboard renders the backend analysis (no mock data in the component).
    expect(await screen.findByText('Assay Capabilities Catalogue')).toBeInTheDocument();
    expect(screen.getByText('Tiny superscripts', { exact: false })).toBeInTheDocument();
    await user.click(screen.getByRole('tab', { name: 'Design analysis' }));
    expect(screen.getByText('#191F5B ≈')).toBeInTheDocument();
    expect(screen.getByText('not inferable')).toBeInTheDocument();
    expect(screen.getByText('Hero cover')).toBeInTheDocument();
    await user.click(screen.getByRole('tab', { name: 'Comparative strategy' }));
    const items = screen.getAllByText(/^(Cover|Contents)$/).map((n) => n.textContent);
    expect(items).toEqual(['Cover', 'Contents']);
    expect(screen.getByText('Section opener band')).toBeInTheDocument();
  });

  it('locks inputs while an analysis is running', async () => {
    routes['POST /api/projects'] = () => ({ status: 202, body: project('queued', 1) });
    routes['GET /api/projects/abc123abc123abc123abc123abc123ab'] = () => ({ body: project('running', 3) });
    const user = userEvent.setup();
    render(<Studio pollMs={5} />);
    await screen.findByText('Connected · gemini-test');
    await addBoth(user);
    await user.click(screen.getByRole('button', { name: 'Start analysis' }));
    expect(await screen.findByRole('button', { name: 'Analysis running…' })).toBeDisabled();
    expect(screen.getAllByRole('button', { name: 'Replace' })[0]).toBeDisabled();
    expect(await screen.findByText('Analysing content authority')).toBeInTheDocument();
    expect(screen.getByText('in progress')).toBeInTheDocument();
  });

  it('shows a failed analysis with its error', async () => {
    routes['POST /api/projects'] = () => ({ status: 202, body: project('queued', 1) });
    routes['GET /api/projects/abc123abc123abc123abc123abc123ab'] = () => ({
      body: project('failed', 3, { error: { kind: 'quota', message: 'Gemini quota or rate limit exceeded.' } }),
    });
    const user = userEvent.setup();
    render(<Studio pollMs={5} />);
    await screen.findByText('Connected · gemini-test');
    await addBoth(user);
    await user.click(screen.getByRole('button', { name: 'Start analysis' }));
    expect(await screen.findByText('Analysis failed')).toBeInTheDocument();
    expect(screen.getByText('Gemini rate limit or quota reached')).toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'Downloads' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'New analysis' })).toBeInTheDocument();
  });

  it('shows an error when the backend rejects the upload', async () => {
    routes['POST /api/projects'] = () => ({ status: 413, body: { detail: 'Content Authority exceeds the 50 MB upload limit.' } });
    const user = userEvent.setup();
    render(<Studio pollMs={5} />);
    await screen.findByText('Connected · gemini-test');
    await addBoth(user);
    await user.click(screen.getByRole('button', { name: 'Start analysis' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Content Authority exceeds the 50 MB upload limit.');
    expect(screen.getByRole('button', { name: 'Start analysis' })).toBeEnabled();
  });

  it('disables start when no outputs are selected', async () => {
    const user = userEvent.setup();
    render(<Studio pollMs={5} />);
    await screen.findByText('Connected · gemini-test');
    await addBoth(user);
    for (const label of [/Complete Claude Skill ZIP/, /Standalone SKILL.md/, /Structured analysis JSON/]) await user.click(screen.getByLabelText(label));
    expect(screen.getAllByText('Select at least one output.').length).toBeGreaterThan(0);
    expect(screen.getByRole('button', { name: 'Start analysis' })).toBeDisabled();
  });
});
