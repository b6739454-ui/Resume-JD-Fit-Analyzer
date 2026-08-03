import React, { useState, useRef } from 'react';

interface InputZoneProps {
  resumeText: string;
  jdText: string;
  onResumeChange: (v: string) => void;
  onJdChange: (v: string) => void;
  onAnalyzeText: () => void;
  onAnalyzeFile: (resumeFile: File, jdFile: File) => void;
  isLoading: boolean;
}

type InputMode = 'text' | 'file';

const InputZone: React.FC<InputZoneProps> = ({
  resumeText,
  jdText,
  onResumeChange,
  onJdChange,
  onAnalyzeText,
  onAnalyzeFile,
  isLoading,
}) => {
  const [mode, setMode] = useState<InputMode>('text');
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [jdFile, setJdFile] = useState<File | null>(null);

  const [resumeDragOver, setResumeDragOver] = useState(false);
  const [jdDragOver, setJdDragOver] = useState(false);

  const resumeInputRef = useRef<HTMLInputElement>(null);
  const jdInputRef = useRef<HTMLInputElement>(null);

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const handleFileDrop = (
    e: React.DragEvent<HTMLDivElement>,
    target: 'resume' | 'jd'
  ) => {
    e.preventDefault();
    if (target === 'resume') setResumeDragOver(false);
    if (target === 'jd') setJdDragOver(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      if (target === 'resume') setResumeFile(file);
      else setJdFile(file);
    }
  };

  const handleDragOver = (
    e: React.DragEvent<HTMLDivElement>,
    target: 'resume' | 'jd'
  ) => {
    e.preventDefault();
    if (target === 'resume') setResumeDragOver(true);
    if (target === 'jd') setJdDragOver(true);
  };

  const handleDragLeave = (
    e: React.DragEvent<HTMLDivElement>,
    target: 'resume' | 'jd'
  ) => {
    e.preventDefault();
    if (target === 'resume') setResumeDragOver(false);
    if (target === 'jd') setJdDragOver(false);
  };

  const handleSubmit = () => {
    if (mode === 'text') {
      onAnalyzeText();
    } else if (resumeFile && jdFile) {
      onAnalyzeFile(resumeFile, jdFile);
    }
  };

  const isSubmitDisabled =
    isLoading ||
    (mode === 'text' && (!resumeText.trim() || !jdText.trim())) ||
    (mode === 'file' && (!resumeFile || !jdFile));

  return (
    <section className="input-zone">
      {/* Toggle mode bar */}
      <div className="mode-toggle">
        <button
          type="button"
          className={`mode-toggle-btn ${mode === 'text' ? 'active' : ''}`}
          onClick={() => setMode('text')}
          disabled={isLoading}
        >
          📝 Paste text
        </button>
        <button
          type="button"
          className={`mode-toggle-btn ${mode === 'file' ? 'active' : ''}`}
          onClick={() => setMode('file')}
          disabled={isLoading}
        >
          📄 Upload PDF / DOCX
        </button>
      </div>

      {mode === 'text' ? (
        <div className="input-grid">
          <div className="input-col">
            <label className="input-label" htmlFor="resume-input">
              Resume <span className="input-label-hint">(plain text)</span>
            </label>
            <textarea
              id="resume-input"
              className="textarea"
              placeholder="Paste resume text here…"
              value={resumeText}
              onChange={(e) => onResumeChange(e.target.value)}
              rows={16}
              disabled={isLoading}
            />
          </div>
          <div className="input-col">
            <label className="input-label" htmlFor="jd-input">
              Job Description <span className="input-label-hint">(plain text)</span>
            </label>
            <textarea
              id="jd-input"
              className="textarea"
              placeholder="Paste job description text here…"
              value={jdText}
              onChange={(e) => onJdChange(e.target.value)}
              rows={16}
              disabled={isLoading}
            />
          </div>
        </div>
      ) : (
        <div className="input-grid">
          {/* Resume file upload */}
          <div className="input-col">
            <label className="input-label">Resume File (.pdf, .docx)</label>
            <input
              type="file"
              ref={resumeInputRef}
              accept=".pdf,.docx,.txt"
              style={{ display: 'none' }}
              onChange={(e) => {
                if (e.target.files?.[0]) setResumeFile(e.target.files[0]);
              }}
            />
            {resumeFile ? (
              <div className="file-preview-card">
                <div className="file-info">
                  <div className="file-icon">📄</div>
                  <div>
                    <div className="file-name">{resumeFile.name}</div>
                    <div className="file-size">{formatFileSize(resumeFile.size)}</div>
                  </div>
                </div>
                <button
                  type="button"
                  className="btn-remove-file"
                  onClick={() => setResumeFile(null)}
                  disabled={isLoading}
                >
                  ✕ Remove
                </button>
              </div>
            ) : (
              <div
                className={`file-dropzone ${resumeDragOver ? 'drag-over' : ''}`}
                onDrop={(e) => handleFileDrop(e, 'resume')}
                onDragOver={(e) => handleDragOver(e, 'resume')}
                onDragLeave={(e) => handleDragLeave(e, 'resume')}
                onClick={() => resumeInputRef.current?.click()}
              >
                <div className="file-dropzone-icon">📤</div>
                <div className="file-dropzone-title">Click to upload or drag & drop Resume</div>
                <div className="file-dropzone-subtitle">Supports PDF, DOCX, TXT</div>
              </div>
            )}
          </div>

          {/* JD file upload */}
          <div className="input-col">
            <label className="input-label">Job Description File (.pdf, .docx)</label>
            <input
              type="file"
              ref={jdInputRef}
              accept=".pdf,.docx,.txt"
              style={{ display: 'none' }}
              onChange={(e) => {
                if (e.target.files?.[0]) setJdFile(e.target.files[0]);
              }}
            />
            {jdFile ? (
              <div className="file-preview-card">
                <div className="file-info">
                  <div className="file-icon">💼</div>
                  <div>
                    <div className="file-name">{jdFile.name}</div>
                    <div className="file-size">{formatFileSize(jdFile.size)}</div>
                  </div>
                </div>
                <button
                  type="button"
                  className="btn-remove-file"
                  onClick={() => setJdFile(null)}
                  disabled={isLoading}
                >
                  ✕ Remove
                </button>
              </div>
            ) : (
              <div
                className={`file-dropzone ${jdDragOver ? 'drag-over' : ''}`}
                onDrop={(e) => handleFileDrop(e, 'jd')}
                onDragOver={(e) => handleDragOver(e, 'jd')}
                onDragLeave={(e) => handleDragLeave(e, 'jd')}
                onClick={() => jdInputRef.current?.click()}
              >
                <div className="file-dropzone-icon">📤</div>
                <div className="file-dropzone-title">Click to upload or drag & drop Job Description</div>
                <div className="file-dropzone-subtitle">Supports PDF, DOCX, TXT</div>
              </div>
            )}
          </div>
        </div>
      )}

      <div className="input-actions">
        <button
          id="analyze-btn"
          className="btn-primary"
          onClick={handleSubmit}
          disabled={isSubmitDisabled}
        >
          {isLoading ? (
            <>
              <span className="spinner" /> Analyzing…
            </>
          ) : (
            '⚡ Analyze Fit'
          )}
        </button>
      </div>
    </section>
  );
};

export default InputZone;
