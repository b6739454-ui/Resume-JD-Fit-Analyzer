import React from 'react';

interface BiasBannerProps {
  disclaimer: string;
}

const IconShield = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M12 2l7 4v6c0 5-3.5 8.5-7 10-3.5-1.5-7-5-7-10V6l7-4z" />
    <path d="M9 12l2 2 4-4" />
  </svg>
);

const BiasBanner: React.FC<BiasBannerProps> = ({ disclaimer }) => (
  <div className="bias-banner" role="alert">
    <div className="bias-banner-icon" aria-hidden="true"><IconShield /></div>
    <div className="bias-banner-content">
      <span className="bias-banner-title">Human Oversight Required</span>
      <p className="bias-banner-text">{disclaimer}</p>
    </div>
  </div>
);

export default BiasBanner;
