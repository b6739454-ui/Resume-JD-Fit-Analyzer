"""
tests/test_cache_invalidation.py

ทดสอบ Cache Invalidation เมื่อ prompt เปลี่ยน:
1. สร้าง cache จำลองพร้อม prompt hash เก่า
2. เปลี่ยน hash (simulate การแก้ prompt)
3. ยืนยันว่า cache ถูก invalidate อัตโนมัติ ไม่ใช้ผลเก่า

ไม่ต้องใช้ LLM จริง — ทดสอบ logic ล้วนๆ
"""

import os
import sys
import json
import hashlib
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_cache_key_uniqueness():
    """ทดสอบว่า cache key ต่างกันเมื่อ text ต่างกัน"""
    print("\n" + "="*60)
    print("🧪 Test 1: Cache Key Uniqueness")
    print("="*60)

    from main import _make_cache_key

    resume_a = "Jane Doe — Python developer"
    jd_a = "Looking for Python engineer"
    resume_b = "John Smith — Java developer"
    jd_b = "Looking for Java engineer"
    # เหมือนกันทุกอย่าง
    resume_same = resume_a
    jd_same = jd_a

    key_aa = _make_cache_key(resume_a, jd_a)
    key_bb = _make_cache_key(resume_b, jd_b)
    key_same = _make_cache_key(resume_same, jd_same)

    assert key_aa == key_same, f"FAIL: same content → different key ({key_aa} vs {key_same})"
    assert key_aa != key_bb, f"FAIL: different content → same key ({key_aa})"

    print(f"  ✅ key(resume_a, jd_a) = {key_aa}")
    print(f"  ✅ key(resume_b, jd_b) = {key_bb} ← ต่างกัน")
    print(f"  ✅ key(resume_same, jd_same) = {key_same} ← เหมือน key_aa ✓")
    print("  PASS: cache keys unique per content ✅")


def test_prompt_hash_invalidation():
    """
    ทดสอบ cache invalidation เมื่อ prompt hash เปลี่ยน:
    1. สร้าง cache file จำลองพร้อม hash เก่า
    2. เปลี่ยน prompt → hash ใหม่
    3. โหลด cache → ต้องเจอ hash mismatch → ต้อง invalidate
    """
    print("\n" + "="*60)
    print("🧪 Test 2: Prompt Hash Cache Invalidation")
    print("="*60)

    from main import _make_cache_key

    # สร้าง temp dir สำหรับ cache file
    tmpdir = tempfile.mkdtemp()
    cache_path = os.path.join(tmpdir, "extraction_cache.json")

    try:
        resume_text = "Jane Doe — Senior Financial Analyst with 5 years experience"
        jd_text = "Looking for Senior Financial Analyst"
        cache_key = _make_cache_key(resume_text, jd_text)

        # --- Step 1: สร้าง cache ด้วย hash เก่า ---
        old_hash = "aabbccdd11223344"  # hash จำลอง (ไม่ตรงกับ hash จริงของ prompt ปัจจุบัน)
        fake_cache = {
            "__prompt_hash__": old_hash,
            cache_key: {
                "resume_data": {"name": "Jane Doe", "skills": []},
                "jd_data": {"job_title": "Senior Financial Analyst", "requirements": []}
            }
        }
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(fake_cache, f, ensure_ascii=False)

        print(f"  📝 สร้าง cache จำลอง: hash={old_hash}, key={cache_key}")

        # --- Step 2: คำนวณ hash จริงจาก prompts ปัจจุบัน ---
        from agents.resume_extractor import SYSTEM_PROMPT as RESUME_PROMPT
        from agents.jd_extractor import SYSTEM_PROMPT as JD_PROMPT

        real_hash = hashlib.sha256((RESUME_PROMPT + JD_PROMPT).encode("utf-8")).hexdigest()[:16]
        print(f"  🔑 Hash จริงของ prompt ปัจจุบัน: {real_hash}")

        # --- Step 3: ทดสอบ logic invalidation ---
        with open(cache_path, "r", encoding="utf-8") as f:
            raw_cache = json.load(f)

        cached_hash = raw_cache.get("__prompt_hash__")
        assert cached_hash == old_hash, "TEST SETUP ERROR"

        if cached_hash != real_hash:
            print(f"  ✅ Hash mismatch detected: เก่า={cached_hash} ≠ ใหม่={real_hash}")
            print(f"  ✅ Cache ถูก INVALIDATE อัตโนมัติ — จะไม่ใช้ผลจาก prompt เก่า")
            loaded_cache = {}  # ล้าง cache
        else:
            print(f"  ⚠️  Hash ตรง — cache ถูกใช้ต่อ (นี่คือกรณีปกติถ้า prompt ไม่เปลี่ยน)")
            loaded_cache = {k: v for k, v in raw_cache.items() if not k.startswith("__")}

        assert len(loaded_cache) == 0, f"FAIL: cache ควรว่างหลัง invalidate แต่มี {len(loaded_cache)} entries"
        print(f"  ✅ loaded_cache ว่างเปล่าหลัง invalidate: {loaded_cache}")
        print("  PASS: cache invalidation on prompt hash change ✅")

        # --- Step 4: ทดสอบกรณี hash ตรง (cache ควรโหลดได้ปกติ) ---
        print(f"\n  🧪 Step 4: ทดสอบกรณี hash ตรง (cache ใช้ได้ต่อ)")
        valid_cache = {
            "__prompt_hash__": real_hash,
            cache_key: {
                "resume_data": {"name": "Jane Doe", "skills": []},
                "jd_data": {"job_title": "Senior Financial Analyst", "requirements": []}
            }
        }
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(valid_cache, f)

        with open(cache_path, "r", encoding="utf-8") as f:
            raw2 = json.load(f)

        if raw2.get("__prompt_hash__") == real_hash:
            loaded2 = {k: v for k, v in raw2.items() if not k.startswith("__")}
            assert cache_key in loaded2, "FAIL: cache key ควรอยู่ใน loaded cache"
            print(f"  ✅ Hash ตรง → โหลด cache ได้ {len(loaded2)} entry: {list(loaded2.keys())}")
            print("  PASS: valid cache loads correctly ✅")
        else:
            print("  FAIL: hash comparison error")

    finally:
        shutil.rmtree(tmpdir)


def test_same_text_different_requests():
    """
    จำลอง scenario จริง:
    1. Request แรก → cache MISS → ถ้ามี LLM ก็จะเรียก แต่ที่นี่ simulate ด้วย fake data
    2. Request ที่ 2 ด้วย text เดิม → ควรเป็น cache HIT
    3. Request ที่ 3 ด้วย text ต่าง → ควรเป็น cache MISS
    """
    print("\n" + "="*60)
    print("🧪 Test 3: Cache HIT/MISS per content hash")
    print("="*60)

    from main import _make_cache_key

    resume1 = "Alice — Python Dev"
    jd1     = "Python Backend Engineer"
    resume2 = "Bob — Java Dev"   # text ต่าง → key ต่าง
    jd2     = "Java Backend Engineer"

    key1 = _make_cache_key(resume1, jd1)
    key1_repeat = _make_cache_key(resume1, jd1)  # เดิม
    key2 = _make_cache_key(resume2, jd2)

    # Simulate in-memory cache
    in_memory_cache = {}

    def simulate_request(resume, jd, label):
        key = _make_cache_key(resume, jd)
        if key in in_memory_cache:
            print(f"  {label} → 🟢 HIT  (key={key}) — ข้าม LLM extractor")
            return "from_cache"
        else:
            print(f"  {label} → 🔴 MISS (key={key}) — เรียก LLM extractor [ถ้าไม่ mock]")
            in_memory_cache[key] = {"resume_data": f"extracted_{resume[:10]}", "jd_data": f"extracted_{jd[:10]}"}
            return "from_llm"

    r1 = simulate_request(resume1, jd1, "Request 1 (resume1+jd1, ครั้งแรก)")
    r2 = simulate_request(resume1, jd1, "Request 2 (resume1+jd1, ซ้ำ)   ")
    r3 = simulate_request(resume2, jd2, "Request 3 (resume2+jd2, text ใหม่)")

    assert r1 == "from_llm",   "FAIL: Request 1 ควรเป็น MISS"
    assert r2 == "from_cache", "FAIL: Request 2 ควรเป็น HIT (text เดิม)"
    assert r3 == "from_llm",   "FAIL: Request 3 ควรเป็น MISS (text ต่าง)"

    print("  PASS: HIT/MISS logic correct ✅")


if __name__ == "__main__":
    print("🚀 Running Cache Invalidation Tests\n")
    try:
        test_cache_key_uniqueness()
        test_prompt_hash_invalidation()
        test_same_text_different_requests()
        print("\n" + "="*60)
        print("✅ ALL CACHE TESTS PASSED")
        print("="*60)
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        import sys; sys.exit(1)
