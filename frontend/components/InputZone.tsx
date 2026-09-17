import React, { useState, useRef } from 'react';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
type InputMode = 'text' | 'file';

export type AnalyzePayload =
  | { resumeMode: 'text'; resumeText: string; jdMode: 'text'; jdText: string }
  | { resumeMode: 'text'; resumeText: string; jdMode: 'file'; jdFile: File }
  | { resumeMode: 'file'; resumeFile: File; jdMode: 'text'; jdText: string }
  | { resumeMode: 'file'; resumeFile: File; jdMode: 'file'; jdFile: File };

interface InputZoneProps {
  resumeText: string;
  jdText: string;
  onResumeChange: (v: string) => void;
  onJdChange: (v: string) => void;
  onAnalyze: (payload: AnalyzePayload) => void;
  isLoading: boolean;
}

// ---------------------------------------------------------------------------
// Icons
// ---------------------------------------------------------------------------
const IconText = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
    <path d="M14 2v6h6" />
    <path d="M8 13h8" />
    <path d="M8 17h8" />
    <path d="M8 9h2" />
  </svg>
);
const IconUpload = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
    <path d="M17 8l-5-5-5 5" />
    <path d="M12 3v12" />
  </svg>
);
const IconFile = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
    <path d="M14 2v6h6" />
  </svg>
);
const IconBriefcase = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <rect x="2" y="7" width="20" height="14" rx="2" />
    <path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2" />
    <path d="M2 12h20" />
  </svg>
);
const IconCloud = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
    <path d="M17 8l-5-5-5 5" />
    <path d="M12 3v12" />
  </svg>
);
const IconX = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
    <path d="M18 6L6 18" />
    <path d="M6 6l12 12" />
  </svg>
);
const IconSpark = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M12 3l1.6 4.4L18 9l-4.4 1.6L12 15l-1.6-4.4L6 9l4.4-1.6L12 3z" />
    <path d="M19 13l1 2.2L22 16l-2 0.8L19 19l-1-2.2L16 16l2-0.8L19 13z" />
    <path d="M5 14l1 2.2L8 17l-2 0.8L5 20l-1-2.2L2 17l2-0.8L5 14z" />
  </svg>
);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
const formatFileSize = (bytes: number): string => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

/** Mini tab switcher rendered inside each card header */
const CardModeToggle: React.FC<{
  mode: InputMode;
  onChange: (m: InputMode) => void;
  disabled: boolean;
}> = ({ mode, onChange, disabled }) => (
  <div className="card-mode-toggle">
    <button
      type="button"
      className={`card-mode-btn ${mode === 'text' ? 'active' : ''}`}
      onClick={() => onChange('text')}
      disabled={disabled}
    >
      <IconText /> Paste text
    </button>
    <button
      type="button"
      className={`card-mode-btn ${mode === 'file' ? 'active' : ''}`}
      onClick={() => onChange('file')}
      disabled={disabled}
    >
      <IconUpload /> Upload file
    </button>
  </div>
);

/** Drop-zone + hidden file input for one card */
const FileUploadPanel: React.FC<{
  label: string;
  isResume: boolean;
  file: File | null;
  onFile: (f: File) => void;
  onClear: () => void;
  disabled: boolean;
}> = ({ label, isResume, file, onFile, onClear, disabled }) => {
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragOver(false);
    const dropped = e.dataTransfer.files?.[0];
    if (dropped) onFile(dropped);
  };

  return (
    <>
      <input
        type="file"
        ref={inputRef}
        accept=".pdf,.docx,.txt"
        style={{ display: 'none' }}
        onChange={(e) => {
          if (e.target.files?.[0]) onFile(e.target.files[0]);
        }}
      />
      {file ? (
        <div className="file-preview-card">
          <div className="file-info">
            <div className="file-icon">{isResume ? <IconFile /> : <IconBriefcase />}</div>
            <div>
              <div className="file-name">{file.name}</div>
              <div className="file-size">{formatFileSize(file.size)}</div>
            </div>
          </div>
          <button
            type="button"
            className="btn-remove-file"
            onClick={onClear}
            disabled={disabled}
          >
            <IconX /> Remove
          </button>
        </div>
      ) : (
        <div
          className={`file-dropzone ${dragOver ? 'drag-over' : ''}`}
          onDrop={handleDrop}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={(e) => { e.preventDefault(); setDragOver(false); }}
          onClick={() => inputRef.current?.click()}
        >
          <div className="file-dropzone-icon"><IconCloud /></div>
          <div className="file-dropzone-title">
            Click to upload or drag &amp; drop {label}
          </div>
          <div className="file-dropzone-subtitle">Supports PDF, DOCX, TXT</div>
        </div>
      )}
    </>
  );
};

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------
const InputZone: React.FC<InputZoneProps> = ({
  resumeText,
  jdText,
  onResumeChange,
  onJdChange,
  onAnalyze,
  isLoading,
}) => {
  const [resumeMode, setResumeMode] = useState<InputMode>('text');
  const [jdMode, setJdMode]         = useState<InputMode>('text');
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [jdFile, setJdFile]         = useState<File | null>(null);

  const handleResumeModeChange = (m: InputMode) => {
    setResumeMode(m);
    if (m === 'text') setResumeFile(null);
  };
  const handleJdModeChange = (m: InputMode) => {
    setJdMode(m);
    if (m === 'text') setJdFile(null);
  };

  const isResumeReady = resumeMode === 'text' ? resumeText.trim() !== '' : resumeFile !== null;
  const isJdReady     = jdMode     === 'text' ? jdText.trim()     !== '' : jdFile     !== null;
  const isSubmitDisabled = isLoading || !isResumeReady || !isJdReady;

  const handleSubmit = () => {
    if (resumeMode === 'text' && jdMode === 'text') {
      onAnalyze({ resumeMode: 'text', resumeText, jdMode: 'text', jdText });
    } else if (resumeMode === 'text' && jdMode === 'file' && jdFile) {
      onAnalyze({ resumeMode: 'text', resumeText, jdMode: 'file', jdFile });
    } else if (resumeMode === 'file' && resumeFile && jdMode === 'text') {
      onAnalyze({ resumeMode: 'file', resumeFile, jdMode: 'text', jdText });
    } else if (resumeMode === 'file' && resumeFile && jdMode === 'file' && jdFile) {
      onAnalyze({ resumeMode: 'file', resumeFile, jdMode: 'file', jdFile });
    }
  };

  return (
    <section className="input-zone">
      <div className="input-grid">

        {/* ── Resume Card ─────────────────────────────── */}
        <div className="input-col">
          <div className="card-header">
            <label className="input-label">
              <IconFile /> Resume
            </label>
            <CardModeToggle
              mode={resumeMode}
              onChange={handleResumeModeChange}
              disabled={isLoading}
            />
          </div>

          {resumeMode === 'text' ? (
            <textarea
              id="resume-input"
              className="textarea"
              placeholder="Paste resume text here…"
              value={resumeText}
              onChange={(e) => onResumeChange(e.target.value)}
              rows={16}
              disabled={isLoading}
            />
          ) : (
            <FileUploadPanel
              label="Resume"
              isResume={true}
              file={resumeFile}
              onFile={setResumeFile}
              onClear={() => setResumeFile(null)}
              disabled={isLoading}
            />
          )}
        </div>

        {/* ── Job Description Card ─────────────────────── */}
        <div className="input-col">
          <div className="card-header">
            <label className="input-label">
              <IconBriefcase /> Job Description
            </label>
            <CardModeToggle
              mode={jdMode}
              onChange={handleJdModeChange}
              disabled={isLoading}
            />
          </div>

          {jdMode === 'text' ? (
            <textarea
              id="jd-input"
              className="textarea"
              placeholder="Paste job description text here…"
              value={jdText}
              onChange={(e) => onJdChange(e.target.value)}
              rows={16}
              disabled={isLoading}
            />
          ) : (
            <FileUploadPanel
              label="Job Description"
              isResume={false}
              file={jdFile}
              onFile={setJdFile}
              onClear={() => setJdFile(null)}
              disabled={isLoading}
            />
          )}
        </div>

      </div>

      <div className="input-actions">
        <button
          id="analyze-btn"
          className="btn-primary"
          onClick={handleSubmit}
          disabled={isSubmitDisabled}
        >
          {isLoading ? (
            <>
              <span className="spinner" aria-hidden="true" /> Analyzing…
            </>
          ) : (
            <>
              <IconSpark /> Analyze Fit
            </>
          )}
        </button>
      </div>
    </section>
  );
};

export default InputZone;
