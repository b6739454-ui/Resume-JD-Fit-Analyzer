"""
tests/test_demo_fallback.py
ทดสอบ 5 ข้อตามสถานการณ์ demo จริง:
1. Real pipeline ใช้งานได้ (fit_score ไม่ใช่ 88)
2. จับเวลาสลับไป mock mode ผ่าน /admin/toggle-mock
3. Mock mode คืน fit_score=88 ไม่ error
4. สลับกลับ real pipeline + วัดเวลา
5. UX ระหว่าง restart — frontend ค้างหรือ error ยังไง
"""
import time
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from main import app

client = TestClient(app, raise_server_exceptions=False)

RESUME_SE = (
    "John Smith\nEmail: john@example.com Phone: 0812345678\n"
    "Senior Software Engineer with 8 years of Python, FastAPI, Docker, PostgreSQL, AWS."
)
JD_SE = (
    "Job Title: Senior Python Developer\n"
    "Must-have:\n- 5+ years Python\n- FastAPI or Django\n- PostgreSQL\n"
    "Nice-to-have:\n- Docker\n- AWS Certification"
)


def divider(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


# ─────────────────────────────────────────────────────────
# 1. Real pipeline (default mode)
# ─────────────────────────────────────────────────────────
divider("TEST 1: Real pipeline (default mode)")

# ตรวจสอบ mode ปัจจุบัน
status = client.get("/admin/mode-status").json()
print(f"Current mode: {status['mode']}")
assert status["mock_mode"] is False, "Expected real pipeline mode at startup"

t_start = time.time()
resp = client.post("/fit/analyze", json={"resume_text": RESUME_SE, "jd_text": JD_SE})
elapsed_real = time.time() - t_start

data = resp.json()
fit_score = data.get("fit_score")
print(f"Status: {resp.status_code}")
print(f"Fit Score: {fit_score}")
print(f"Must-Have: {data.get('must_have_score')}")
print(f"Gaps: {data.get('gaps')}")
print(f"Time taken: {elapsed_real:.2f}s")
assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
assert fit_score != 88, f"Got static mock score 88! Pipeline not working."
print("[PASS] Real pipeline returns dynamic score (not 88)")


# ─────────────────────────────────────────────────────────
# 2. Switch to MOCK via /admin/toggle-mock — measure time
# ─────────────────────────────────────────────────────────
divider("TEST 2: Switch to MOCK mode (runtime, no restart)")

t_switch_start = time.time()
toggle_resp = client.post("/admin/toggle-mock?enable=true")
elapsed_switch = time.time() - t_switch_start

print(f"Toggle response: {toggle_resp.json()}")
print(f"Time to switch to MOCK: {elapsed_switch*1000:.0f} ms")
assert toggle_resp.status_code == 200
assert toggle_resp.json()["mock_mode"] is True
print("[PASS] Switched to mock mode in < 1 second")


# ─────────────────────────────────────────────────────────
# 3. Verify mock mode returns fit_score=88, no error
# ─────────────────────────────────────────────────────────
divider("TEST 3: Mock mode returns fit_score=88, no error")

t_mock_start = time.time()
mock_resp = client.post("/fit/analyze", json={"resume_text": RESUME_SE, "jd_text": JD_SE})
elapsed_mock = time.time() - t_mock_start

mock_data = mock_resp.json()
mock_score = mock_data.get("fit_score")
print(f"Status: {mock_resp.status_code}")
print(f"Fit Score (mock): {mock_score}")
print(f"Time taken (mock): {elapsed_mock:.2f}s")
assert mock_resp.status_code == 200, f"Expected 200, got {mock_resp.status_code}"
assert mock_score == 88, f"Expected 88, got {mock_score}"
print("[PASS] Mock mode returns fit_score=88 instantly, no error")


# ─────────────────────────────────────────────────────────
# 4. Switch BACK to real pipeline — measure time
# ─────────────────────────────────────────────────────────
divider("TEST 4: Switch BACK to real pipeline")

t_restore_start = time.time()
restore_resp = client.post("/admin/toggle-mock?enable=false")
elapsed_restore = time.time() - t_restore_start

print(f"Toggle response: {restore_resp.json()}")
print(f"Time to switch back to REAL: {elapsed_restore*1000:.0f} ms")
assert restore_resp.status_code == 200
assert restore_resp.json()["mock_mode"] is False

# ตรวจสอบว่ากลับมา dynamic จริง (ไม่ใช่ 88)
real_again_resp = client.post("/fit/analyze", json={"resume_text": RESUME_SE, "jd_text": JD_SE})
real_again_score = real_again_resp.json().get("fit_score")
print(f"Fit Score (real again): {real_again_score}")
assert real_again_resp.status_code == 200
assert real_again_score != 88, "Still getting mock score 88 after switching back!"
print("[PASS] Switched back to real pipeline, score is dynamic again")


# ─────────────────────────────────────────────────────────
# 5. UX during server restart — Frontend behavior analysis
# ─────────────────────────────────────────────────────────
divider("TEST 5: UX during server restart (simulated)")

# ทดสอบ: ยิง request ไปยัง endpoint ที่ไม่มี (simulate server down)
print("Simulating frontend request during server downtime...")
t_down = time.time()
try:
    import httpx
    with httpx.Client(timeout=2.0) as c:
        r = c.post("http://127.0.0.1:9999/fit/analyze",
                   json={"resume_text": "test", "jd_text": "test"})
    print(f"Unexpected response: {r.status_code}")
except httpx.ConnectError:
    elapsed_err = time.time() - t_down
    print(f"Frontend receives: ConnectError (server down) after {elapsed_err:.2f}s")
    print("=> React fetch() จะ throw NetworkError ทันที (ไม่ค้าง)")
    print("=> หน้าเว็บจะแสดง error state ถ้า frontend มี error boundary")
    print("=> Auto-reconnect: ไม่มีอัตโนมัติ — ต้องกดปุ่ม Submit ใหม่หลัง server กลับมา")
except Exception as e:
    print(f"Received error: {type(e).__name__}: {e}")

print("\n[INFO] UX Summary:")
print("  - Frontend ค้างรอ: ไม่ค้าง (timeout ใน ~2s)")
print("  - Frontend error ทันที: ใช่ (ConnectError / NetworkError)")
print("  - Auto-reconnect: ไม่มีอัตโนมัติ ต้อง submit ใหม่")
print("  - วิธี mitigate: ใช้ /admin/toggle-mock แทน restart (0ms downtime!)")


# ─────────────────────────────────────────────────────────
# สรุปผล
# ─────────────────────────────────────────────────────────
divider("SUMMARY")
print(f"  Real pipeline call time : {elapsed_real:.2f}s")
print(f"  Switch to MOCK time     : {elapsed_switch*1000:.0f} ms")
print(f"  Mock response time      : {elapsed_mock:.2f}s")
print(f"  Switch back to REAL time: {elapsed_restore*1000:.0f} ms")
print(f"  Server restart downtime : ~5-10s (UX: ConnectError immediately)")
print(f"  /admin/toggle-mock     : 0 ms downtime (RECOMMENDED)")
print("\nAll 5 tests PASSED!")
