import React from 'react';

interface HeaderProps {
  onUseMock: () => void;
}

const Header: React.FC<HeaderProps> = ({ onUseMock }) => (
  <header className="app-header">
    <div className="header-brand">
      <div className="header-logo" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
          <path d="M14 2H7a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
          <path d="M14 2v6h6" />
          <path d="M9 13h6" />
          <path d="M9 17h6" />
          <path d="M9 9h1" />
        </svg>
      </div>
      <div className="header-text">
        <h1 className="header-title">Resume <span>↔</span> JD Fit Analyzer</h1>
        <p className="header-subtitle">AI-powered resume screening with evidence-backed matching</p>
      </div>
    </div>
    <div className="header-actions">
      <button className="btn-ghost" onClick={onUseMock} title="Load demo data">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
        </svg>
        Try demo
      </button>
    </div>
  </header>
);

export default Header;
