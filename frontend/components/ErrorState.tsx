import React from 'react';

interface ErrorStateProps {
  message: string;
  onRetry?: () => void;
}

/** จำแนก error type จาก message และคืน user-friendly Thai message */
function parseErrorMessage(raw: string): { title: string; body: string; isRateLimit: boolean } {
  const lower = raw.toLowerCase();

  // 503 / high demand / rate limit / quota
  if (
    lower.includes('503') ||
    lower.includes('high demand') ||
    lower.includes('unavailable') ||
    lower.includes('429') ||
    lower.includes('quota') ||
    lower.includes('resource_exhausted') ||
    lower.includes('rate limit') ||
    lower.includes('หนาแน่น') ||
    lower.includes('ระบบกำลังมีผู้ใช้งานจำนวนมาก')
  ) {
    return {
      title: 'ระบบกำลังหนาแน่นชั่วคราว',
      body: 'Google Gemini API มีผู้ใช้งานจำนวนมากในขณะนี้ กรุณารอ 1-2 นาทีแล้วลองวิเคราะห์ใหม่อีกครั้ง\n\nหรือเปิด Mock Mode ผ่าน POST /admin/toggle-mock?enable=true เพื่อทดสอบ UI ระหว่างรอ',
      isRateLimit: true,
    };
  }

  // 400 / validation
  if (lower.includes('400') || lower.includes('ว่างเปล่า') || lower.includes('invalid')) {
    return {
      title: 'ข้อมูลไม่ถูกต้อง',
      body: raw,
      isRateLimit: false,
    };
  }

  // network
  if (lower.includes('network') || lower.includes('fetch') || lower.includes('failed to fetch')) {
    return {
      title: 'ไม่สามารถเชื่อมต่อกับ server ได้',
      body: 'กรุณาตรวจสอบว่า backend รันอยู่ที่ http://localhost:8000 แล้วลองใหม่',
      isRateLimit: false,
    };
  }

  // timeout
  if (lower.includes('timeout') || lower.includes('timed out')) {
    return {
      title: 'หมดเวลารอ (Timeout)',
      body: 'การวิเคราะห์ใช้เวลานานเกินกำหนด กรุณาลองใหม่หรือใช้ Mock Mode สำหรับทดสอบ UI',
      isRateLimit: false,
    };
  }

  // default
  return {
    title: 'เกิดข้อผิดพลาด',
    body: raw,
    isRateLimit: false,
  };
}

const ErrorState: React.FC<ErrorStateProps> = ({ message, onRetry }) => {
  const { title, body, isRateLimit } = parseErrorMessage(message);

  return (
    <div className="error-state-card" role="alert">
      <div className="error-icon">{isRateLimit ? '⏳' : '❌'}</div>
      <h3 className="error-title">{title}</h3>
      <p className="error-message" style={{ whiteSpace: 'pre-line' }}>{body}</p>
      {isRateLimit && (
        <p className="error-hint">
          💡 <strong>เคล็ดลับ:</strong> รัน server แบบ{' '}
          <code>uvicorn main:app --port 8000</code> (ไม่มี <code>--reload</code>)
          เพื่อป้องกัน embedding โหลดซ้ำและประหยัด quota
        </p>
      )}
      {onRetry && (
        <button className="btn-secondary" onClick={onRetry}>
          🔄 ลองใหม่อีกครั้ง
        </button>
      )}
    </div>
  );
};

export default ErrorState;
