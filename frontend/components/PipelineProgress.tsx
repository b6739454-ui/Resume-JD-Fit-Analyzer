import React from 'react';
import type { PipelineStep } from '../types';

interface PipelineProgressProps {
  steps: PipelineStep[];
  elapsedSeconds?: number;
  isLoading?: boolean;
}

function getWaitMessage(elapsed: number): string {
  if (elapsed < 30) return 'กำลังวิเคราะห์ข้อมูล…';
  if (elapsed < 90) return 'กำลังประมวลผล (หากเซิร์ฟเวอร์ AI มีผู้ใช้งานหนาแน่น ระบบกำลังรอ backoff 30–60s และ retry อัตโนมัติ)…';
  if (elapsed < 180) return 'ระบบกำลังเปรียบเทียบทักษะอย่างละเอียดและจัดการ rate limit กรุณารอสักครู่…';
  return 'ใกล้เสร็จแล้ว ขอบคุณที่รอ';
}

const IconClock = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7v5l3 3" />
  </svg>
);

const IconCheck = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M5 13l4 4L19 7" />
  </svg>
);

const IconAlert = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M12 8v5" />
    <path d="M12 16h.01" />
    <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
  </svg>
);

const PipelineProgress: React.FC<PipelineProgressProps> = ({ steps, elapsedSeconds = 0, isLoading = false }) => (
  <div className="pipeline-progress-container">
    <div className="pipeline-steps">
      {steps.map((step) => {
        let badgeClass = 'step-idle';
        if (step.status === 'running') badgeClass = 'step-running';
        else if (step.status === 'done') badgeClass = 'step-done';
        else if (step.status === 'error') badgeClass = 'step-error';

        const renderIndicator = () => {
          if (step.status === 'running') {
            return (
              <span className="step-indicator step-indicator--running" aria-hidden="true">
                <span className="step-spinner" />
              </span>
            );
          }
          if (step.status === 'done') {
            return (
              <span className="step-indicator step-indicator--done" aria-hidden="true">
                <IconCheck />
              </span>
            );
          }
          if (step.status === 'error') {
            return (
              <span className="step-indicator step-indicator--error" aria-hidden="true">
                <IconAlert />
              </span>
            );
          }
          return <span className="step-indicator step-indicator--idle" aria-hidden="true" />;
        };

        return (
          <div key={step.id} className={`pipeline-step ${badgeClass}`}>
            {renderIndicator()}
            <span className="step-label">{step.label}</span>
          </div>
        );
      })}
    </div>

    {isLoading && (
      <div className="pipeline-timing">
        <div className="progress-bar-track" aria-hidden="true">
          <div className="progress-bar-indeterminate" />
        </div>
        <div className="pipeline-elapsed">
          <span className="elapsed-icon" aria-hidden="true"><IconClock /></span>
          <span className="elapsed-text">
            {getWaitMessage(elapsedSeconds)}
          </span>
          <span className="elapsed-seconds">
            {elapsedSeconds}s
          </span>
        </div>
      </div>
    )}
  </div>
);

export default PipelineProgress;
