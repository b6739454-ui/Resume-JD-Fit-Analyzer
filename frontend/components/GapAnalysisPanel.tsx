import React from 'react';

interface GapAnalysisPanelProps {
  gaps: string[];
  suggestedQuestions: string[];
}

const GapAnalysisPanel: React.FC<GapAnalysisPanelProps> = ({
  gaps,
  suggestedQuestions,
}) => (
  <section className="gap-analysis-panel">
    <div className="panel-block">
      <h3 className="panel-title">
        <span className="panel-icon">⚠️</span> Identified Skill Gaps ({gaps.length})
      </h3>
      {gaps.length === 0 ? (
        <p className="empty-text">No skill gaps identified. Candidate satisfies requirements.</p>
      ) : (
        <div className="gap-chips-container">
          {gaps.map((gapSkill, index) => (
            <span key={index} className="gap-chip">
              {gapSkill}
            </span>
          ))}
        </div>
      )}
    </div>

    <div className="panel-block">
      <h3 className="panel-title">
        <span className="panel-icon">💡</span> Suggested Interview Questions ({suggestedQuestions.length})
      </h3>
      {suggestedQuestions.length === 0 ? (
        <p className="empty-text">No interview questions generated.</p>
      ) : (
        <ol className="questions-list">
          {suggestedQuestions.map((q, idx) => (
            <li key={idx} className="question-item">
              <span className="question-num">{idx + 1}.</span>
              <span className="question-text">{q}</span>
            </li>
          ))}
        </ol>
      )}
    </div>
  </section>
);

export default GapAnalysisPanel;
