/**
 * mockData.ts
 *
 * NOTE: DEFAULT_MOCK_REPORT was removed as per Architectural Refactoring.
 * Backend (main.py /fit/analyze) is the SINGLE SOURCE OF TRUTH for all fit report responses.
 * Frontend App.tsx always calls POST /fit/analyze instead of returning static local mock data.
 */
