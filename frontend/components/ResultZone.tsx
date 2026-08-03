import React from 'react';
import type { FitReportData } from '../types';
import FitScoreSection from './FitScoreSection';
import SkillMatrixSection from './SkillMatrixSection';
import GapAnalysisPanel from './GapAnalysisPanel';
import BiasBanner from './BiasBanner';

interface ResultZoneProps {
  report: FitReportData;
}

const ResultZone: React.FC<ResultZoneProps> = ({ report }) => (
  <div className="result-zone">
    <FitScoreSection
      fitScore={report.fit_score}
      mustHaveScore={report.must_have_score}
      niceToHaveScore={report.nice_to_have_score}
    />

    <BiasBanner disclaimer={report.bias_disclaimer} />

    <SkillMatrixSection matches={report.matches} />

    <GapAnalysisPanel
      gaps={report.gaps}
      suggestedQuestions={report.suggested_interview_questions}
    />
  </div>
);

export default ResultZone;
