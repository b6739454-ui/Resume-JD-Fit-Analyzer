import { useState } from 'react';
import type { FitReportData, PipelineStep } from './types';
import Header from './components/Header';
import InputZone from './components/InputZone';
import PipelineProgress from './components/PipelineProgress';
import ResultZone from './components/ResultZone';
import ErrorState from './components/ErrorState';

const INITIAL_PIPELINE_STEPS: PipelineStep[] = [
  { id: 'resume_extractor', label: '1. Resume Extractor', status: 'idle' },
  { id: 'jd_extractor', label: '2. JD Extractor', status: 'idle' },
  { id: 'fit_analyzer', label: '3. Fit Analyzer', status: 'idle' },
  { id: 'gap_agent', label: '4. Gap Agent', status: 'idle' },
  { id: 'judge_agent', label: '5. Judge Agent', status: 'idle' },
];

export function App() {
  const [resumeText, setResumeText] = useState('');
  const [jdText, setJdText] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<FitReportData | null>(null);
  const [pipelineSteps, setPipelineSteps] = useState<PipelineStep[]>(INITIAL_PIPELINE_STEPS);

  const runAnalysis = async (resume: string, jd: string) => {
    if (!resume.trim() || !jd.trim()) return;

    setIsLoading(true);
    setError(null);
    setReport(null);

    // Set initial running state
    setPipelineSteps([
      { id: 'resume_extractor', label: '1. Resume Extractor', status: 'running' },
      { id: 'jd_extractor', label: '2. JD Extractor', status: 'running' },
      { id: 'fit_analyzer', label: '3. Fit Analyzer', status: 'running' },
      { id: 'gap_agent', label: '4. Gap Agent', status: 'running' },
      { id: 'judge_agent', label: '5. Judge Agent', status: 'running' },
    ]);

    try {
      const response = await fetch('/fit/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          resume_text: resume,
          jd_text: jd,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Network response was not ok' }));
        throw new Error(errorData.detail || `Server error: ${response.status}`);
      }

      const data: FitReportData = await response.json();
      setReport(data);

      setPipelineSteps(
        INITIAL_PIPELINE_STEPS.map((s) => ({ ...s, status: 'done' }))
      );
    } catch (err: any) {
      setError(err.message || 'An unexpected error occurred during analysis.');
      setPipelineSteps(
        INITIAL_PIPELINE_STEPS.map((s) => ({ ...s, status: 'error' }))
      );
    } finally {
      setIsLoading(false);
    }
  };

  const runAnalysisFile = async (resumeFile: File, jdFile: File) => {
    setIsLoading(true);
    setError(null);
    setReport(null);

    setPipelineSteps([
      { id: 'resume_extractor', label: '1. Resume Extractor', status: 'running' },
      { id: 'jd_extractor', label: '2. JD Extractor', status: 'running' },
      { id: 'fit_analyzer', label: '3. Fit Analyzer', status: 'running' },
      { id: 'gap_agent', label: '4. Gap Agent', status: 'running' },
      { id: 'judge_agent', label: '5. Judge Agent', status: 'running' },
    ]);

    try {
      const formData = new FormData();
      formData.append('resume_file', resumeFile);
      formData.append('jd_file', jdFile);

      const response = await fetch('/fit/analyze-file', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Network response was not ok' }));
        throw new Error(errorData.detail || `Server error: ${response.status}`);
      }

      const data: FitReportData = await response.json();
      setReport(data);

      setPipelineSteps(
        INITIAL_PIPELINE_STEPS.map((s) => ({ ...s, status: 'done' }))
      );
    } catch (err: any) {
      setError(err.message || 'An unexpected error occurred during analysis.');
      setPipelineSteps(
        INITIAL_PIPELINE_STEPS.map((s) => ({ ...s, status: 'error' }))
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleAnalyzeText = () => runAnalysis(resumeText, jdText);

  const handleUseMock = () => {
    const sampleResume =
      'Jane Doe\nSenior Financial Analyst\n\nExperience:\n- 5+ years of financial planning and analysis experience in IT budget management\n- Led SOX audit documentation and control testing for three consecutive fiscal years\n- Presented quarterly budget summaries to department leads\n- Built automated Excel dashboards with VBA macros for month-end close\n- Basic familiarity with Power BI for reporting\n\nEducation:\n- Master of Business Administration: Finance';
    const sampleJd =
      'Senior Financial Analyst Required Qualifications:\n- 5+ years of financial planning and analysis experience\n- Experience with Sarbanes-Oxley (SOX) audit\n- Experience presenting to executive leadership\n- Capital budget cycle development\n\nNice to have:\n- Advanced Excel / VBA skills\n- Experience with Power BI or Tableau\n- CPA certification';

    setResumeText(sampleResume);
    setJdText(sampleJd);
    runAnalysis(sampleResume, sampleJd);
  };

  return (
    <div className="app-container">
      <Header onUseMock={handleUseMock} />

      <main className="main-content">
        <InputZone
          resumeText={resumeText}
          jdText={jdText}
          onResumeChange={setResumeText}
          onJdChange={setJdText}
          onAnalyzeText={handleAnalyzeText}
          onAnalyzeFile={runAnalysisFile}
          isLoading={isLoading}
        />

        {(isLoading || report || error) && (
          <PipelineProgress steps={pipelineSteps} />
        )}

        {error && <ErrorState message={error} onRetry={handleAnalyzeText} />}

        {report && !isLoading && <ResultZone report={report} />}
      </main>
    </div>
  );
}

export default App;
