import React from 'react';

interface HeaderProps {
  onUseMock: () => void;
}

const Header: React.FC<HeaderProps> = ({ onUseMock }) => (
  <header className="app-header">
    <div className="header-brand">
      <div className="header-icon">📋</div>
      <div>
        <h1 className="header-title">Resume ↔ JD Fit Analyzer</h1>
        <p className="header-subtitle">AI-powered resume screening with evidence-backed matching</p>
      </div>
    </div>
    <button className="btn-ghost" onClick={onUseMock} title="Load demo data">
      Try demo
    </button>
  </header>
);

export default Header;
