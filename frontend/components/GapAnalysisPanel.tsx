import React from 'react';

interface GapAnalysisPanelProps {
  gaps: string[];
  suggestedQuestions: string[];
}

const IconAlert = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M12 8v5" />
    <path d="M12 16h.01" />
    <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
  </svg>
);

const IconLightbulb = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M9 21h6" />
    <path d="M12 3a5 5 0 0 0-5 5c0 2.1 1.2 3.9 2.8 4.8L10 14h4l.2-1.2A5 5 0 0 0 17 8a5 5 0 0 0-5-5z" />
    <path d="M9 18h6" />
  </svg>
);

const GapAnalysisPanel: React.FC<GapAnalysisPanelProps> = ({
  gaps,
  suggestedQuestions,
}) => (
  <section className="gap-analysis-panel">
    <div className="panel-block">
      <h3 className="panel-title">
        <span className="panel-icon panel-icon--gap" aria-hidden="true"><IconAlert /></span>
        Identified Skill Gaps ({gaps.length})
      </h3>
      {gaps.length === 0 ? (
        <p className="empty-text">No skill gaps identified. Candidate satisfies requirements.</p>
      ) : (
        <div className="gap-chips-container">
          {gaps.map((gapSkill, index) => (
            <span key={index} className="gap-chip" style={{ animationDelay: `${index * 45}ms` }}>
              {gapSkill}
            </span>
          ))}
        </div>
      )}
    </div>

    <div className="panel-block">
      <h3 className="panel-title">
        <span className="panel-icon panel-icon--qa" aria-hidden="true"><IconLightbulb /></span>
        Suggested Interview Questions ({suggestedQuestions.length})
      </h3>
      {suggestedQuestions.length === 0 ? (
        <p className="empty-text">No interview questions generated.</p>
      ) : (
        <ol className="questions-list">
          {suggestedQuestions.map((q, idx) => (
            <li key={idx} className="question-item" style={{ animationDelay: `${idx * 70}ms` }}>
              <span className="question-num">{idx + 1}</span>
              <span className="question-text">{q}</span>
            </li>
          ))}
        </ol>
      )}
    </div>
  </section>
);

export default GapAnalysisPanel;
