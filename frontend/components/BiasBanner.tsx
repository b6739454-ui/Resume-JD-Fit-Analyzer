import React from 'react';

interface BiasBannerProps {
  disclaimer: string;
}

const BiasBanner: React.FC<BiasBannerProps> = ({ disclaimer }) => (
  <div className="bias-banner" role="alert">
    <div className="bias-banner-icon">⚠️</div>
    <div className="bias-banner-content">
      <span className="bias-banner-title">Human Oversight Required</span>
      <p className="bias-banner-text">{disclaimer}</p>
    </div>
  </div>
);

export default BiasBanner;
