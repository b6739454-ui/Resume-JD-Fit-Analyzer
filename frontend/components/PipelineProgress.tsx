import React from 'react';
import type { PipelineStep } from '../types';

interface PipelineProgressProps {
  steps: PipelineStep[];
  elapsedSeconds?: number;
  isLoading?: boolean;
}

/** คืนข้อความให้กำลังใจตามเวลาที่รอไปแล้ว */
function getWaitMessage(elapsed: number): string {
  if (elapsed < 30) return 'กำลังวิเคราะห์...';
  if (elapsed < 90) return 'กำลังประมวลผล อาจใช้เวลา 1-3 นาที...';
  if (elapsed < 180) return 'ระบบกำลังเปรียบเทียบ skill อย่างละเอียด กรุณารอสักครู่...';
  return 'ใกล้เสร็จแล้ว ขอบคุณที่รอ 🙏';
}

const PipelineProgress: React.FC<PipelineProgressProps> = ({ steps, elapsedSeconds = 0, isLoading = false }) => (
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

    {/* Progress bar + elapsed time — แสดงเฉพาะตอน loading */}
    {isLoading && (
      <div className="pipeline-timing">
        <div className="progress-bar-track">
          <div className="progress-bar-indeterminate" />
        </div>
        <div className="pipeline-elapsed">
          <span className="elapsed-icon">⏱</span>
          <span className="elapsed-text">
            {getWaitMessage(elapsedSeconds)}
          </span>
          <span className="elapsed-seconds">
            ({elapsedSeconds}s)
          </span>
        </div>
      </div>
    )}
  </div>
);

export default PipelineProgress;
