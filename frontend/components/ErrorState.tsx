import React from 'react';

interface ErrorStateProps {
  message: string;
  onRetry?: () => void;
}

const ErrorState: React.FC<ErrorStateProps> = ({ message, onRetry }) => (
  <div className="error-state-card" role="alert">
    <div className="error-icon">❌</div>
    <h3 className="error-title">Analysis Failed</h3>
    <p className="error-message">{message}</p>
    {onRetry && (
      <button className="btn-secondary" onClick={onRetry}>
        Try Again
      </button>
    )}
  </div>
);

export default ErrorState;
