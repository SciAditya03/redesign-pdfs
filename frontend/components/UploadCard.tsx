'use client';

import { useId, useRef, useState } from 'react';
import type { PdfInfo } from '../lib/api';
import { formatBytes } from '../lib/format';

export type SlotState =
  | { status: 'empty' }
  | { status: 'checking'; file: File }
  | { status: 'ready'; file: File; info: PdfInfo }
  | { status: 'error'; file: File | null; error: string };

type Props = {
  index: string;
  role: string;
  title: string;
  description: string;
  slot: SlotState;
  disabled?: boolean;
  onSelect: (file: File) => void;
  onRemove: () => void;
};

export function UploadCard({ index, role, title, description, slot, disabled, onSelect, onRemove }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const inputId = useId();
  const [dragging, setDragging] = useState(false);
  const file = slot.status === 'empty' ? null : slot.file;

  function pick(files: FileList | null) {
    const f = files?.[0];
    if (f) onSelect(f);
    if (inputRef.current) inputRef.current.value = '';
  }

  return (
    <section className={`upload-card ${slot.status}`} aria-labelledby={`${inputId}-title`}>
      <header className="upload-head">
        <span className="eyebrow">
          {index} — {role}
        </span>
        <h2 id={`${inputId}-title`}>{title}</h2>
        <p>{description}</p>
      </header>

      <input
        ref={inputRef}
        id={inputId}
        type="file"
        accept="application/pdf,.pdf"
        className="visually-hidden"
        aria-label={`${role} PDF`}
        disabled={disabled}
        onChange={(e) => pick(e.target.files)}
      />

      {!file ? (
        <label
          htmlFor={inputId}
          className={`dropzone ${dragging ? 'dragging' : ''} ${disabled ? 'disabled' : ''}`}
          onDragOver={(e) => {
            e.preventDefault();
            if (!disabled) setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            if (!disabled) pick(e.dataTransfer.files);
          }}
        >
          <PdfIcon />
          <span className="dz-title">Drop a PDF here</span>
          <span className="dz-sub">
            or <span className="link-like">browse files</span>
          </span>
        </label>
      ) : (
        <div className="file-row">
          <PdfIcon small />
          <div className="file-meta">
            <div className="file-name" title={file.name}>
              {file.name}
            </div>
            <div className="file-facts">
              {formatBytes(file.size)}
              {slot.status === 'ready' && (
                <>
                  {' · '}
                  {slot.info.page_count} {slot.info.page_count === 1 ? 'page' : 'pages'}
                </>
              )}
              {slot.status === 'checking' && ' · checking…'}
            </div>
          </div>
          <div className="file-actions">
            <button type="button" className="btn-ghost" disabled={disabled} onClick={() => inputRef.current?.click()}>
              Replace
            </button>
            <button type="button" className="btn-ghost" disabled={disabled} onClick={onRemove} aria-label={`Remove ${role} PDF`}>
              Remove
            </button>
          </div>
        </div>
      )}

      <div className="slot-feedback" role="status" aria-live="polite">
        {slot.status === 'ready' && (
          <span className="ok">
            Valid PDF
            {slot.info.likely_scanned && (
              <span className="warn"> · Little extractable text: this may be a scanned document. Gemini will read it visually, but check the results carefully.</span>
            )}
          </span>
        )}
        {slot.status === 'error' && <span className="err">{slot.error}</span>}
        {slot.status === 'error' && !slot.file && (
          <button type="button" className="btn-ghost" onClick={onRemove}>
            Dismiss
          </button>
        )}
      </div>
    </section>
  );
}

function PdfIcon({ small }: { small?: boolean }) {
  const s = small ? 28 : 40;
  return (
    <svg width={s} height={s} viewBox="0 0 40 40" aria-hidden="true" className="pdf-icon">
      <path d="M10 4h14l8 8v22a2 2 0 0 1-2 2H10a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z" fill="var(--surface-2)" stroke="var(--line-strong)" />
      <path d="M24 4v8h8" fill="none" stroke="var(--line-strong)" />
      <rect x="11" y="21" width="18" height="8" rx="2" fill="var(--accent)" />
      <text x="20" y="27.2" textAnchor="middle" fontSize="6" fontWeight="700" fill="#fff" fontFamily="inherit">
        PDF
      </text>
    </svg>
  );
}
