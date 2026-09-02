import { useState, useEffect, useRef } from 'react';
import type { FitReportData, PipelineStep } from './types';
import type { AnalyzePayload } from './components/InputZone';
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

const RUNNING_STEPS: PipelineStep[] = INITIAL_PIPELINE_STEPS.map((s) => ({
  ...s,
  status: 'running',
}));

export function App() {
  const [resumeText, setResumeText] = useState('');
  const [jdText, setJdText] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<FitReportData | null>(null);
  const [pipelineSteps, setPipelineSteps] = useState<PipelineStep[]>(INITIAL_PIPELINE_STEPS);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);


  // -------------------------------------------------------------------------
  // Elapsed timer helpers
  // -------------------------------------------------------------------------
  const startTimer = () => {
    setElapsedSeconds(0);
    if (intervalRef.current) clearInterval(intervalRef.current);
    intervalRef.current = setInterval(() => {
      setElapsedSeconds((s) => s + 1);
    }, 1000);
  };

  const stopTimer = () => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  };

  // Cleanup on unmount
  useEffect(() => () => stopTimer(), []);

  // -------------------------------------------------------------------------
  // Core pipeline runner — accepts pre-resolved text strings
  // -------------------------------------------------------------------------
  const runPipeline = async (resume: string, jd: string) => {
    if (!resume.trim() || !jd.trim()) return;

    setIsLoading(true);
    setError(null);
    setReport(null);
    setPipelineSteps(RUNNING_STEPS);
    startTimer();

    try {
      const response = await fetch('/fit/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ resume_text: resume, jd_text: jd }),
      });

      if (!response.ok) {
        const errorData = await response
          .json()
          .catch(() => ({ detail: 'Network response was not ok' }));
        throw new Error(errorData.detail || `Server error: ${response.status}`);
      }

      const data: FitReportData = await response.json();
      setReport(data);
      setPipelineSteps(INITIAL_PIPELINE_STEPS.map((s) => ({ ...s, status: 'done' })));
    } catch (err: any) {
      setError(err.message || 'An unexpected error occurred during analysis.');
      setPipelineSteps(INITIAL_PIPELINE_STEPS.map((s) => ({ ...s, status: 'error' })));
    } finally {
      stopTimer();
      setIsLoading(false);
    }
  };


  // -------------------------------------------------------------------------
  // File pipeline runner — accepts a FormData with resume_file + jd_file
  // -------------------------------------------------------------------------
  const runFilePipeline = async (formData: FormData) => {
    setIsLoading(true);
    setError(null);
    setReport(null);
    setPipelineSteps(RUNNING_STEPS);
    startTimer();

    try {
      const response = await fetch('/fit/analyze-file', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response
          .json()
          .catch(() => ({ detail: 'Network response was not ok' }));
        throw new Error(errorData.detail || `Server error: ${response.status}`);
      }

      const data: FitReportData = await response.json();
      setReport(data);
      setPipelineSteps(INITIAL_PIPELINE_STEPS.map((s) => ({ ...s, status: 'done' })));
    } catch (err: any) {
      setError(err.message || 'An unexpected error occurred during analysis.');
      setPipelineSteps(INITIAL_PIPELINE_STEPS.map((s) => ({ ...s, status: 'error' })));
    } finally {
      stopTimer();
      setIsLoading(false);
    }
  };


  // -------------------------------------------------------------------------
  // Unified handler — routes text-only → JSON, everything else → FormData
  // Mixed case: text side is converted to a .txt Blob so we can reuse the
  // existing /fit/analyze-file endpoint without any backend changes.
  // -------------------------------------------------------------------------
  const handleAnalyze = (payload: AnalyzePayload) => {
    if (payload.resumeMode === 'text' && payload.jdMode === 'text') {
      // Both text → lightweight JSON endpoint
      runPipeline(payload.resumeText, payload.jdText);
    } else {
      // At least one side is a file → use multipart FormData
      const formData = new FormData();

      if (payload.resumeMode === 'file') {
        formData.append('resume_file', payload.resumeFile);
      } else {
        // Convert plain text to a .txt Blob so the backend can extract it
        const blob = new Blob([payload.resumeText], { type: 'text/plain' });
        formData.append('resume_file', blob, 'resume.txt');
      }

      if (payload.jdMode === 'file') {
        formData.append('jd_file', payload.jdFile);
      } else {
        const blob = new Blob([payload.jdText], { type: 'text/plain' });
        formData.append('jd_file', blob, 'job_description.txt');
      }

      runFilePipeline(formData);
    }
  };

  // -------------------------------------------------------------------------
  // Mock / demo helper
  // -------------------------------------------------------------------------
  const handleUseMock = () => {
    const sampleResume =
      'Jane Doe\nSenior Financial Analyst\n\nExperience:\n- 5+ years of financial planning and analysis experience in IT budget management\n- Led SOX audit documentation and control testing for three consecutive fiscal years\n- Presented quarterly budget summaries to department leads\n- Built automated Excel dashboards with VBA macros for month-end close\n- Basic familiarity with Power BI for reporting\n\nEducation:\n- Master of Business Administration: Finance';
    const sampleJd =
      'Senior Financial Analyst Required Qualifications:\n- 5+ years of financial planning and analysis experience\n- Experience with Sarbanes-Oxley (SOX) audit\n- Experience presenting to executive leadership\n- Capital budget cycle development\n\nNice to have:\n- Advanced Excel / VBA skills\n- Experience with Power BI or Tableau\n- CPA certification';

    setResumeText(sampleResume);
    setJdText(sampleJd);
    runPipeline(sampleResume, sampleJd);
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
          onAnalyze={handleAnalyze}
          isLoading={isLoading}
        />

        {(isLoading || report || error) && (
          <PipelineProgress
            steps={pipelineSteps}
            elapsedSeconds={elapsedSeconds}
            isLoading={isLoading}
          />
        )}

        {error && <ErrorState message={error} onRetry={() => handleAnalyze({ resumeMode: 'text', resumeText, jdMode: 'text', jdText })} />}

        {report && !isLoading && <ResultZone report={report} />}
      </main>
    </div>
  );
}

export default App;
