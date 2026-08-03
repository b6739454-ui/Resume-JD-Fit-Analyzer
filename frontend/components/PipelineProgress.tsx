import React from 'react';
import type { PipelineStep } from '../types';

interface PipelineProgressProps {
  steps: PipelineStep[];
}

const PipelineProgress: React.FC<PipelineProgressProps> = ({ steps }) => (
  <div className="pipeline-progress-container">
    <div className="pipeline-steps">
      {steps.map((step) => {
        let badgeClass = 'step-idle';
        let icon = '⚪';
        if (step.status === 'running') {
          badgeClass = 'step-running';
          icon = '⏳';
        } else if (step.status === 'done') {
          badgeClass = 'step-done';
          icon = '✅';
        } else if (step.status === 'error') {
          badgeClass = 'step-error';
          icon = '❌';
        }

        return (
          <div key={step.id} className={`pipeline-step ${badgeClass}`}>
            <span className="step-icon">{icon}</span>
            <span className="step-label">{step.label}</span>
          </div>
        );
      })}
    </div>
  </div>
);

export default PipelineProgress;
