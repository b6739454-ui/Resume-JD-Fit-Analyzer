import React from 'react';

interface FitScoreSectionProps {
  fitScore: number;
  mustHaveScore: number;
  niceToHaveScore: number;
}

const FitScoreSection: React.FC<FitScoreSectionProps> = ({
  fitScore,
  mustHaveScore,
  niceToHaveScore,
}) => {
  const getScoreColor = (score: number) => {
    if (score >= 80) return 'score-high';
    if (score >= 60) return 'score-medium';
    return 'score-low';
  };

  return (
    <section className="fit-score-section">
      <div className="main-score-card">
        <div className={`score-badge-circle ${getScoreColor(fitScore)}`}>
          <span className="score-number">{fitScore}</span>
          <span className="score-max">/100</span>
        </div>
        <div className="score-meta">
          <h2 className="score-title">Overall Fit Score</h2>
          <p className="score-desc">Weighted score (70% Must-Have + 30% Nice-to-Have)</p>
        </div>
      </div>

      <div className="sub-scores-grid">
        <div className="sub-score-card">
          <div className="sub-score-header">
            <span className="sub-score-label">Must-Have Score</span>
            <span className={`sub-score-val ${getScoreColor(mustHaveScore)}`}>
              {mustHaveScore}%
            </span>
          </div>
          <div className="progress-bar-bg">
            <div
              className={`progress-bar-fill ${getScoreColor(mustHaveScore)}`}
              style={{ width: `${mustHaveScore}%` }}
            />
          </div>
        </div>

        <div className="sub-score-card">
          <div className="sub-score-header">
            <span className="sub-score-label">Nice-to-Have Score</span>
            <span className={`sub-score-val ${getScoreColor(niceToHaveScore)}`}>
              {niceToHaveScore}%
            </span>
          </div>
          <div className="progress-bar-bg">
            <div
              className={`progress-bar-fill ${getScoreColor(niceToHaveScore)}`}
              style={{ width: `${niceToHaveScore}%` }}
            />
          </div>
        </div>
      </div>
    </section>
  );
};

export default FitScoreSection;
