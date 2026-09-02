"""
tests/benchmark_reload_vs_noreload.py

วัดเวลา embedding load + server response แบบ:
1. Cold start (จำลอง --reload ที่ spawn process ใหม่ทุกครั้ง)  
2. Warm cache (จำลอง --no-reload ที่ process เดิมยังอยู่)

ไม่เรียก LLM จริง (USE_MOCK_PIPELINE=true) เพื่อแยก overhead ของ embedding load ออกจาก LLM latency
"""

import os
import sys
import time
import subprocess
import json
import urllib.request
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SAMPLE_RESUME = """
Jane Doe
Senior Financial Analyst

Experience:
- 5+ years of financial planning and analysis experience in IT budget management
- Led SOX audit documentation and control testing for three consecutive fiscal years
- Presented quarterly budget summaries to department leads
- Built automated Excel dashboards with VBA macros for month-end close

Education:
- Master of Business Administration: Finance
"""

SAMPLE_JD = """
Senior Financial Analyst Required Qualifications:
- 5+ years of financial planning and analysis experience
- Experience with Sarbanes-Oxley (SOX) audit
- Experience presenting to executive leadership
- Capital budget cycle development

Nice to have:
- Advanced Excel / VBA skills
- Experience with Power BI or Tableau
- CPA certification
"""


def hit_analyze_endpoint(port: int = 8000, use_mock: bool = True) -> float:
    """ยิง request ไปที่ /fit/analyze และ return เวลาที่ใช้ (วินาที)"""
    url = f"http://127.0.0.1:{port}/fit/analyze"
    payload = json.dumps({
        "resume_text": SAMPLE_RESUME,
        "jd_text": SAMPLE_JD
    }).encode("utf-8")

    headers = {"Content-Type": "application/json"}

    t_start = time.perf_counter()
    try:
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=300) as resp:
            _ = resp.read()
        elapsed = time.perf_counter() - t_start
        return elapsed
    except urllib.error.URLError as e:
        elapsed = time.perf_counter() - t_start
        print(f"  ⚠️  Request failed after {elapsed:.2f}s: {e}")
        return -1.0


def measure_embedding_load():
    """วัดเวลา cold start ของ SkillNormalizer โดยตรง (ไม่ผ่าน server)"""
    print("\n" + "="*60)
    print("📊 PART A: SkillNormalizer Load Time Measurement")
    print("="*60)

    # ล้าง instance ก่อนเพื่อ simulate cold start
    from agents.skill_normalizer import SkillNormalizer
    SkillNormalizer._instance = None

    print("\n🔴 Cold Start #1 (จำลอง: process ใหม่จาก --reload):")
    normalizer1 = SkillNormalizer()
    t0 = time.perf_counter()
    normalizer1._lazy_load()
    t1 = time.perf_counter()
    cold_time = t1 - t0
    print(f"   ⏱  load_time = {cold_time:.3f}s (นี่คือเวลาที่ชนทุก request ถ้า --reload)")

    print("\n🟢 Warm Cache #2 (จำลอง: process เดิม --no-reload, request 2+):")
    t0 = time.perf_counter()
    normalizer1._lazy_load()  # _loaded=True → return immediately
    t1 = time.perf_counter()
    warm_time = t1 - t0
    print(f"   ⏱  load_time = {warm_time:.6f}s (แทบ 0 — ข้าม load เพราะ _loaded=True)")

    speedup = cold_time / warm_time if warm_time > 0 else float('inf')
    print(f"\n📈 ต่างกัน {speedup:,.0f}x | Cold: {cold_time:.3f}s vs Warm: {warm_time*1000:.2f}ms")
    
    # Normalize test
    print("\n🔤 ทดสอบ normalize() — เช็คว่าทำงานถูกต้องหลัง load:")
    t0 = time.perf_counter()
    result = normalizer1.normalize("Python programming")
    t1 = time.perf_counter()
    print(f"   normalize('Python programming') → {result['normalized']!r} (conf={result['confidence']:.3f}) [{(t1-t0)*1000:.1f}ms]")

    return cold_time, warm_time


def measure_server_requests(port: int = 8000, n_requests: int = 3):
    """วัดเวลา HTTP request ไปที่ server ที่รันอยู่แล้ว (mock mode)"""
    print(f"\n{'='*60}")
    print(f"📊 PART B: HTTP Request Timing (port={port}, mock=True)")
    print(f"{'='*60}")
    print("  (ต้องรัน server ด้วย USE_MOCK_PIPELINE=true ก่อน)")
    print(f"  กำลังยิง {n_requests} requests...")

    times = []
    for i in range(1, n_requests + 1):
        print(f"\n  Request #{i}:", end=" ", flush=True)
        elapsed = hit_analyze_endpoint(port)
        if elapsed >= 0:
            times.append(elapsed)
            label = "🔴 COLD (embedding load!)" if i == 1 else "🟢 WARM (cached)"
            print(f"  {elapsed:.3f}s {label}")
        else:
            print("  FAILED")

    if times:
        print(f"\n  📈 Summary: min={min(times):.3f}s | max={max(times):.3f}s | avg={sum(times)/len(times):.3f}s")
    return times


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["embedding", "server", "all"], default="embedding",
                        help="embedding: วัด load time โดยตรง | server: ยิง HTTP | all: ทั้งคู่")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    if args.mode in ("embedding", "all"):
        cold, warm = measure_embedding_load()
        print(f"\n✅ สรุป Embedding Load:")
        print(f"   --reload  (cold/request): {cold:.3f}s ← ชนทุก request ถ้าไฟล์เปลี่ยน")
        print(f"   --no-reload (warm/cache): {warm*1000:.3f}ms ← โหลดครั้งเดียวทั้ง session")
        print(f"\n   ⚠️  ถ้า cold_time={cold:.1f}s และยิง 10 requests ด้วย --reload")
        print(f"       overhead รวมสูงสุด = {cold*10:.0f}s เพิ่มเติมจาก LLM time")

    if args.mode in ("server", "all"):
        measure_server_requests(args.port)
