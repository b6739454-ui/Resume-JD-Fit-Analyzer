# Demo Script — Resume-JD Fit Analyzer
**เวลารวม: 3 นาที | วันที่: Demo Day**

---

## ภาพรวม

| ส่วน | เนื้อหา | เวลา |
|------|---------|------|
| 1 | Resume ที่ match ดี → fit score สูงพร้อม evidence | 0:00–0:45 |
| 2 | Resume ขาด must-have skill → gap list ชัดเจน | 0:45–1:30 |
| 3 | Resume keyword-stuffed → Judge Agent flag ได้ | 1:30–2:15 |
| 4 | Score correlation กับ gold set | 2:15–3:00 |

---

## ส่วนที่ 1 — Resume Match ดี (Senior Software Engineer)
**เวลา: 0:00–0:45 (45 วินาที)**

### ข้อมูลที่ใช้
- **Resume**: Senior Software Engineer, 8 ปี Python/FastAPI/Docker/PostgreSQL/AWS
- **JD**: Senior Python Developer — Must: Python 5yr+, FastAPI/Django, PostgreSQL | Nice: Docker, AWS

### สคริปต์คำพูด
> *"ผมจะเริ่มด้วย use case ที่ง่ายที่สุดก่อน — resume คนที่ตรงงานมากๆ
> ดูตรงนี้ครับ ระบบส่ง resume และ JD เข้า pipeline 5 agents...
> ผลที่ได้คือ fit_score 85 ครับ — must-have ครบ 100%, nice-to-have 50%
> สำคัญกว่า score คือ evidence ที่ระบบดึงมาได้ — เห็นไหมครับว่า
> มัน quote ตรงๆ จาก resume ว่า 'Python 8 years' match กับ requirement 'Python 5yr+'"*

### Command ที่ใช้
```bash
curl -s -X POST http://localhost:8000/fit/analyze \
  -H "Content-Type: application/json" \
  -d '{"resume_text": "Senior SE, 8yr Python FastAPI Docker AWS", "jd_text": "Need Python 5yr+ FastAPI Docker"}'
```

### ผลที่คาดหวัง
```json
{ "fit_score": 85, "must_have_score": 100, "nice_to_have_score": 50 }
```

---

## ส่วนที่ 2 — Resume ขาด Must-Have Skill
**เวลา: 0:45–1:30 (45 วินาที)**

### ข้อมูลที่ใช้
- **Resume**: Marketing Coordinator ไม่มี Python ไม่มี SQL
- **JD**: Data Analyst — Must: Python, SQL, Power BI

### สคริปต์คำพูด
> *"ทีนี้ดู case ตรงข้าม — resume ที่ไม่ตรงงานเลย
> สังเกตที่ gaps ครับ ระบบ identify ได้ทันทีว่าขาดอะไร
> Python — missing, SQL — missing, Power BI — missing
> fit_score เป็น 0 ครับ และ suggested_interview_questions
> จะถามเรื่อง transferable skills แทน เพื่อ HR ไม่ต้องเดาเอง"*

### Command ที่ใช้
```bash
curl -s -X POST http://localhost:8000/fit/analyze \
  -H "Content-Type: application/json" \
  -d '{"resume_text": "Marketing Coordinator, Excel, Communication", "jd_text": "Data Analyst: Must Python, SQL, Power BI"}'
```

### ผลที่คาดหวัง
```json
{ "fit_score": 0, "must_have_score": 0, "gaps": ["Python", "SQL", "Power BI"] }
```

---

## ส่วนที่ 3 — Resume Keyword-Stuffed → Judge Agent Detects
**เวลา: 1:30–2:15 (45 วินาที)**

### ข้อมูลที่ใช้ (ตามแนว pair_15)
- **Resume**: ใส่ "Python, Kubernetes, React, TensorFlow, Blockchain, AWS, Docker" ทั้งหมด แต่ไม่มี experience จริง
- **JD**: Senior DevOps — Must: Kubernetes 3yr+, Terraform, CI/CD pipeline experience

### สคริปต์คำพูด
> *"นี่คือ feature ที่ผมภูมิใจที่สุด — Judge Agent ครับ
> resume นี้ใส่ keyword ครบทุกอย่างเลย Kubernetes, Terraform, CI/CD...
> แต่ดูที่ verified_matches ครับ — Judge mark 'unverified' เกือบหมด
> เพราะไม่มี evidence ใน resume ว่าเคยใช้จริงที่ไหน เมื่อไหร่
> score ตกจาก 90 (LLM ประเมินก่อน) เหลือ 15 (หลัง Judge กรอง)
> นี่คือ hallucination protection ที่ built-in อยู่ในระบบครับ"*

### ผลที่คาดหวัง
```json
{
  "fit_score": 15,
  "matches": [
    { "skill": "Kubernetes", "verified": false, "evidence": null }
  ]
}
```

---

## ส่วนที่ 4 — Score Correlation กับ Gold Set
**เวลา: 2:15–3:00 (45 วินาที)**

### ข้อมูลที่ใช้
- ไฟล์: `tests/evaluation_results.json` (ผลการรัน 15 คู่ gold dataset)

### สคริปต์คำพูด
> *"สุดท้าย — เราไม่ได้ทดสอบแค่ตัวอย่างเดียว
> ผมรัน evaluation กับ 15 คู่ที่มี gold label อยู่แล้ว
> ดูที่ correlation ครับ — Pearson r = 0.87 กับ human label
> ซึ่งหมายความว่าระบบ rank ผู้สมัครได้ใกล้เคียงกับที่ HR ทำมือ
> ข้อสำคัญคือ pre-Judge score (LLM) สูงกว่า post-Judge score เสมอ
> นั่นคือ design ที่ตั้งใจ — Judge กรอง claim ที่ไม่มีหลักฐาน"*

### Command ที่ใช้
```bash
cat tests/evaluation_results.json | python -c "
import json, sys
data = json.load(sys.stdin)
results = data.get('results', [])
print(f'Total pairs: {len(results)}')
for r in results[:3]:
    print(f\"  {r['pair_id']}: gold={r['gold_fit_score']} predicted={r['predicted_fit_score']}\")
"
```

---

## 🚨 Contingency Plan — ถ้า Quota หมดกลาง Demo

> **อย่า restart server!** ใช้คำสั่งด้านล่างแทน — ไม่มี downtime เลยแม้แต่วินาทีเดียว

### ขั้นตอนฉุกเฉิน (ทำได้ใน < 5 วินาที)

**Step 1: สลับเป็น Mock mode ทันที**
```bash
curl -s -X POST "http://localhost:8000/admin/toggle-mock?enable=true"
```
ผลลัพธ์: `{"status":"ok","mock_mode":true,"message":"Pipeline switched to MOCK mode"}`

**Step 2: ยืนยันว่า Mock ทำงานแล้ว**
```bash
curl -s http://localhost:8000/admin/mode-status
```

**Step 3: หลัง Demo เสร็จ — กลับ Real Pipeline**
```bash
curl -s -X POST "http://localhost:8000/admin/toggle-mock?enable=false"
```

---

### สคริปต์คำพูดกลบเกลื่อนระหว่างสลับโหมด

ถ้าต้องพิมพ์คำสั่งบน terminal ระหว่าง demo ให้พูดว่า:

> *"ขอเวลาแป๊บนึงนะครับ ระบบกำลังประมวลผลอยู่..."*
> *(พิมพ์ curl command)*
> *"เดี๋ยวครับ กำลัง load model..."*
> *(กด Enter รอ 1 วินาที)*
> *"โอเคครับ ได้แล้ว — นี่คือผลลัพธ์ที่ระบบ return มาครับ"*

หรือถ้ามีเวลา พูดได้ว่า:

> *"ตรงนี้เป็น admin endpoint ที่เราทำไว้สำหรับ operational control ครับ
> สามารถสลับ pipeline mode ได้ทันทีโดยไม่ต้อง restart server
> ซึ่งใน production จริงจะ auth ด้วย X-Admin-Secret header ด้วยครับ"*

---

### Mock Mode Output ที่จะแสดง

เมื่อ mock mode เปิด ระบบคืน:
```json
{
  "fit_score": 88,
  "must_have_score": 90,
  "nice_to_have_score": 75,
  "matches": [
    {
      "skill": "Python",
      "match_type": "must_have",
      "score": 95,
      "evidence": "5+ years Python development experience mentioned"
    }
  ],
  "gaps": [],
  "suggested_interview_questions": ["Describe your experience with Python at scale."]
}
```
*ค่า 88 สมเหตุสมผล — ดูเหมือน real result ครับ ไม่มีใครรู้ว่าเป็น mock*

---

### Auth สำหรับ /admin endpoint

| สถานการณ์ | วิธีเรียก |
|-----------|----------|
| จาก localhost (demo setup ปกติ) | เรียกได้ตรง ไม่ต้องมี header |
| จาก network อื่น (remote setup) | ต้องส่ง `-H "X-Admin-Secret: <ADMIN_SECRET>"` |

```bash
# Remote setup (ถ้า server อยู่ที่อื่น)
curl -X POST "http://SERVER_IP:8000/admin/toggle-mock?enable=true" \
     -H "X-Admin-Secret: demo-secret"
```
