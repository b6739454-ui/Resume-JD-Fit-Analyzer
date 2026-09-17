"""
tests/test_retry_logic.py
Unit tests สำหรับ retry logic และ backoff ของ _call_agent_with_rotation ใน main.py:
1. Error 503 (High Demand / Server Overloaded): backoff 30-60s (30s, 45s, 60s) ไม่เผา key
2. Error 429 (Rate Limit / Quota Exhausted): รอ 2s และสลับ key
3. Error อื่นๆ ที่ไม่ใช่ 503/429: raise ทันที
"""

import os
import sys
import unittest
from unittest.mock import patch

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from google.genai.errors import ServerError
from main import _call_agent_with_rotation, _is_503_error, _is_429_error


class TestRetryLogic(unittest.TestCase):

    def setUp(self):
        # กำหนด environment สำหรับทดสอบให้มีหลาย key
        self.env_patcher = patch.dict(os.environ, {
            "GOOGLE_API_KEY": "fake_primary_key",
            "GOOGLE_API_KEY_FRIEND1": "fake_friend1_key",
            "GOOGLE_API_KEY_FRIEND2": "fake_friend2_key",
        })
        self.env_patcher.start()

    def tearDown(self):
        self.env_patcher.stop()

    def test_is_503_detection(self):
        """ตรวจสอบการตรวจจับ 503 / high demand / overloaded"""
        # ServerError instance
        err_server = ServerError(503, {"message": "The model is overloaded. Please try again later."})
        self.assertTrue(_is_503_error(err_server))

        # String patterns
        self.assertTrue(_is_503_error(Exception("503 Service Unavailable")))
        self.assertTrue(_is_503_error(Exception("the model is overloaded")))
        self.assertTrue(_is_503_error(Exception("Gemini high demand backend error")))
        self.assertTrue(_is_503_error(Exception("service_unavailable")))

        # 429 should NOT be 503
        self.assertFalse(_is_503_error(Exception("429 RESOURCE_EXHAUSTED")))
        self.assertFalse(_is_503_error(ValueError("Invalid argument")))

    def test_is_429_detection(self):
        """ตรวจสอบการตรวจจับ 429 / quota / rate limit"""
        self.assertTrue(_is_429_error(Exception("429 RESOURCE_EXHAUSTED")))
        self.assertTrue(_is_429_error(Exception("Quota exceeded for quota metric")))
        self.assertTrue(_is_429_error(Exception("Rate limit reached: too many requests")))

        # 503 should NOT be 429
        self.assertFalse(_is_429_error(Exception("503 Service Unavailable")))
        self.assertFalse(_is_429_error(ValueError("Invalid argument")))

    @patch("main.time.sleep")
    def test_503_backoff_timing_and_budget(self, mock_sleep):
        """
        เมื่อเจอ 503:
        - backoff ต้องเป็น 30-60 วินาที (30s -> 45s -> 60s)
        - ไม่วนลองใหม่ถี่ๆ ทุก 2s
        - หยุดเมื่อครบ 3 ครั้ง (ไม่เผา key วนไปเรื่อยๆ)
        """
        sleep_durations = []
        mock_sleep.side_effect = lambda duration: sleep_durations.append(duration)

        calls = []
        def failing_agent(**kwargs):
            calls.append(kwargs.get("api_key_env_var"))
            raise Exception("503 UNAVAILABLE: The model is overloaded. Please try again later.")

        with self.assertRaises(Exception) as ctx:
            _call_agent_with_rotation(failing_agent)

        self.assertIn("503", str(ctx.exception))
        # ตรวจสอบว่า sleep เป็นช่วง 30-60 วินาทีจริง
        self.assertEqual(len(sleep_durations), 3, f"Expected 3 retries on 503, got {len(sleep_durations)}")
        self.assertEqual(sleep_durations[0], 30, "Attempt 1 backoff must be 30s")
        self.assertEqual(sleep_durations[1], 45, "Attempt 2 backoff must be 45s")
        self.assertEqual(sleep_durations[2], 60, "Attempt 3 backoff must be 60s (capped)")
        # ตรวจสอบว่าเรียก agent ทั้งหมด 4 ครั้ง (1 initial + 3 retries)
        self.assertEqual(len(calls), 4)

    @patch("main.time.sleep")
    def test_503_recovery(self, mock_sleep):
        """
        เมื่อเจอ 503 แล้วลองใหม่รอบที่ 2 สำเร็จ
        - ต้องคืนค่าผลลัพธ์ได้ถูกต้อง
        - sleep รวม 1 ครั้งที่ 30 วินาที
        """
        sleep_durations = []
        mock_sleep.side_effect = lambda duration: sleep_durations.append(duration)

        attempts = 0
        def recovering_agent(**kwargs):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise Exception("503 The model is overloaded")
            return "SUCCESS_RESULT"

        result = _call_agent_with_rotation(recovering_agent)
        self.assertEqual(result, "SUCCESS_RESULT")
        self.assertEqual(attempts, 2)
        self.assertEqual(sleep_durations, [30])

    @patch("main.time.sleep")
    def test_429_fast_rotation(self, mock_sleep):
        """
        เมื่อเจอ 429:
        - ต้องรอสั้นๆ 2s แล้วสลับไปใช้ key ถัดไปทันที
        - ไม่รอ 30-60s เพราะ 429 เป็นข้อจำกัดเฉพาะ key
        """
        sleep_durations = []
        mock_sleep.side_effect = lambda duration: sleep_durations.append(duration)

        keys_used = []
        def agent_fn(**kwargs):
            key = kwargs.get("api_key_env_var")
            keys_used.append(key)
            if key == "GOOGLE_API_KEY":
                raise Exception("429 RESOURCE_EXHAUSTED: quota limit")
            return f"SUCCESS_WITH_{key}"

        result = _call_agent_with_rotation(agent_fn)
        self.assertEqual(result, "SUCCESS_WITH_GOOGLE_API_KEY_FRIEND1")
        # GOOGLE_API_KEY ลอง 2 ครั้ง (รอ 2s ครั้งแรก, แล้วรอ 1s สลับ key)
        self.assertEqual(keys_used, ["GOOGLE_API_KEY", "GOOGLE_API_KEY", "GOOGLE_API_KEY_FRIEND1"])
        self.assertIn(2, sleep_durations)
        self.assertNotIn(30, sleep_durations, "429 should not trigger 30-60s backoff")

    @patch("main.time.sleep")
    def test_non_retryable_error_raises_immediately(self, mock_sleep):
        """
        Error ทั่วไป (เช่น ValueError, AttributeError) ต้อง raise ทันทีโดยไม่ sleep และไม่ retry
        """
        def agent_fn(**kwargs):
            raise ValueError("Data validation failed")

        with self.assertRaises(ValueError):
            _call_agent_with_rotation(agent_fn)

        mock_sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
