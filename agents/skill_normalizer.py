"""
agents/skill_normalizer.py

โมดูลนี้ทำหน้าที่ "Skill Taxonomy Normalization" ตาม milestone week 4-5 ใน PRD
ใช้ skill_taxonomy_master.csv (รวมจาก ESCO + O*NET จริง 22,727 รายการ) เป็นฐานข้อมูลมาตรฐาน
ไม่ใช้ gold dataset เป็น taxonomy เด็ดขาด เพราะจะทำให้ evaluation ไม่สะท้อนความสามารถจริงของระบบ

วิธีทำงาน:
1. โหลด skill_taxonomy_master.csv ครั้งเดียวตอน import (cache ไว้ใน memory)
2. เตรียม embedding ของทุกทักษะในนั้น (คำนวณครั้งเดียว แล้ว cache เป็นไฟล์ .npy ไว้ ไม่ต้องคำนวณซ้ำทุกครั้งที่รัน)
3. เมื่อ Resume/JD Extractor ดึงชื่อ skill แบบอิสระออกมาแล้ว -> ส่งชื่อนั้นมาที่ normalize_skill_name()
   -> ได้ชื่อมาตรฐานที่ใกล้เคียงที่สุดกลับไป (พร้อมคะแนนความมั่นใจ)

การติดตั้ง (รันที่เครื่องเพื่อน ไม่ใช่ sandbox นี้ เพราะที่นี่ไม่มีอินเทอร์เน็ต):
    pip install sentence-transformers numpy pandas

⚠️  หมายเหตุ uvicorn --reload (root cause ของ embedding โหลดซ้ำ):
    Singleton (_instance) ทำงานถูกต้องภายใน process เดียวกัน
    แต่ `uvicorn --reload` สร้าง subprocess ใหม่ทุกครั้งที่ไฟล์เปลี่ยน
    → _instance กลับเป็น None → โหลด embedding ใหม่ทุกครั้ง (~2000s ตาม log)
    วิธีแก้: ใช้ `uvicorn main:app --port 8000` (ไม่ใส่ --reload) ตอน production/demo
"""

import os
import time
import logging
import numpy as np
import pandas as pd
from functools import lru_cache

logger = logging.getLogger(__name__)

# ชี้ไป data/ ที่อยู่ใน project root เสมอ ไม่ขึ้นกับ working directory ตอนรัน
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAXONOMY_CSV_PATH = os.getenv(
    "SKILL_TAXONOMY_PATH",
    os.path.join(_PROJECT_ROOT, "data", "skill_taxonomy_master.csv")
)
EMBEDDING_CACHE_PATH = os.path.join(_PROJECT_ROOT, "data", "skill_taxonomy_embeddings.npy")
MODEL_NAME = "all-MiniLM-L6-v2"  # โมเดลเล็ก เร็ว เพียงพอสำหรับงานนี้ ไม่ต้องใช้ GPU

# threshold ความคล้าย (cosine similarity) ที่ยอมรับว่า "match" กัน
# ค่านี้ต้องปรับจูนจริงกับ evaluate_gold.py -- เริ่มที่ 0.55 แล้วค่อยขยับตามผลจริง
SIMILARITY_THRESHOLD = 0.55


class SkillNormalizer:
    """
    ห่อ logic การ normalize ไว้ในคลาสเดียว โหลดโมเดล+ taxonomy แค่ครั้งแรกที่ใช้งาน (lazy load)
    เพื่อไม่ให้ import ไฟล์นี้แล้วช้าโดยไม่จำเป็น (เช่นตอน unit test ที่ไม่ได้ใช้ normalize จริง)
    """

    _instance = None  # singleton -- โหลดโมเดลหนักๆ แค่ครั้งเดียวทั้งโปรแกรม

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loaded = False
        return cls._instance

    def _lazy_load(self):
        if self._loaded:
            return

        from sentence_transformers import SentenceTransformer

        _t_start = time.perf_counter()

        print(
            "[skill_normalizer] 🔄 เริ่มโหลด taxonomy master + embedding model...\n"
            "  (ถ้าเจอบ่อยทุก request แสดงว่ารันแบบ --reload อยู่ → ให้เปลี่ยนเป็น: uvicorn main:app --port 8000)"
        )
        logger.info("[skill_normalizer] Starting cold-load of taxonomy + embedding model")

        # โหลดตาราง taxonomy master ที่ทำไว้จาก ESCO + O*NET
        self.taxonomy_df = pd.read_csv(TAXONOMY_CSV_PATH)
        # ตัดแถวที่ชื่อซ้ำกันเป๊ะ (คนละ source แต่ชื่อเดียวกัน) เก็บไว้แค่ตัวแรก ลดขนาดตารางค้นหา
        self.taxonomy_df = self.taxonomy_df.drop_duplicates(subset=["normalized_name"]).reset_index(drop=True)

        _t_csv = time.perf_counter()
        logger.info(f"[skill_normalizer] taxonomy CSV loaded in {_t_csv - _t_start:.2f}s ({len(self.taxonomy_df):,} rows)")

        self.model = SentenceTransformer(MODEL_NAME)

        _t_model = time.perf_counter()
        logger.info(f"[skill_normalizer] SentenceTransformer '{MODEL_NAME}' loaded in {_t_model - _t_csv:.2f}s")

        # ถ้ามี embedding cache ที่คำนวณไว้แล้วตรงกับจำนวนแถวปัจจุบัน ให้ใช้ของเดิม ไม่ต้องคำนวณซ้ำ
        if os.path.exists(EMBEDDING_CACHE_PATH):
            cached = np.load(EMBEDDING_CACHE_PATH)
            if cached.shape[0] == len(self.taxonomy_df):
                self.taxonomy_embeddings = cached
                self._loaded = True
                _t_end = time.perf_counter()
                self._load_time_seconds = _t_end - _t_start
                msg = (
                    f"[skill_normalizer] ✅ โหลด embedding cache สำเร็จ ({len(self.taxonomy_df):,} ทักษะ) "
                    f"รวมเวลา {self._load_time_seconds:.2f}s\n"
                    f"  → model load: {_t_model - _t_csv:.2f}s | npy cache load: {_t_end - _t_model:.2f}s"
                )
                print(msg)
                logger.info(f"[skill_normalizer] CACHE HIT — total load time: {self._load_time_seconds:.2f}s")
                return

        # คำนวณ embedding ใหม่ทั้งหมด (ใช้เวลาสักครู่ครั้งแรก ~ไม่กี่นาทีสำหรับ 20,000+ รายการ)
        # ใช้ skill_name + alt_names รวมกันเป็น text เดียวต่อแถว เพื่อให้จับคำพ้องได้ดีขึ้น
        texts = (
            self.taxonomy_df["skill_name"].fillna("")
            + " "
            + self.taxonomy_df["alt_names"].fillna("").str.replace(" | ", " ")
        ).tolist()

        print(f"[skill_normalizer] ⚙️  คำนวณ embedding ใหม่ {len(texts):,} รายการ (อาจใช้เวลาหลายนาที)...")
        self.taxonomy_embeddings = self.model.encode(
            texts, show_progress_bar=True, batch_size=64, normalize_embeddings=True
        )
        np.save(EMBEDDING_CACHE_PATH, self.taxonomy_embeddings)

        self._loaded = True
        _t_end = time.perf_counter()
        self._load_time_seconds = _t_end - _t_start
        msg = (
            f"[skill_normalizer] ✅ คำนวณ embedding เสร็จแล้ว ({len(self.taxonomy_df):,} ทักษะ) "
            f"บันทึก cache ไว้แล้ว รวมเวลา {self._load_time_seconds:.2f}s"
        )
        print(msg)
        logger.info(f"[skill_normalizer] EMBEDDING COMPUTED — total load time: {self._load_time_seconds:.2f}s")

    @property
    def load_time_seconds(self) -> float:
        """คืนค่าเวลาที่ใช้โหลด embedding ครั้งล่าสุด (วินาที) — ใช้ใน health check / monitoring"""
        return getattr(self, "_load_time_seconds", 0.0)



    def normalize(self, raw_skill_name: str) -> dict:
        """
        รับชื่อ skill แบบอิสระ (จาก LLM extraction) -> คืนชื่อมาตรฐานที่ใกล้เคียงที่สุด

        Returns:
            {
                "original": ชื่อเดิมที่ส่งเข้ามา,
                "normalized": ชื่อมาตรฐานที่เจอ (หรือชื่อเดิมถ้าไม่เจอที่คล้ายพอ),
                "confidence": คะแนนความคล้าย 0-1,
                "matched": True/False (True ถ้าความคล้ายผ่าน threshold)
            }
        """
        self._lazy_load()

        query_embedding = self.model.encode([raw_skill_name], normalize_embeddings=True)
        similarities = self.taxonomy_embeddings @ query_embedding[0]  # cosine similarity (เพราะ normalize แล้ว)

        best_idx = int(np.argmax(similarities))
        best_score = float(similarities[best_idx])

        if best_score >= SIMILARITY_THRESHOLD:
            return {
                "original": raw_skill_name,
                "normalized": self.taxonomy_df.iloc[best_idx]["skill_name"],
                "confidence": round(best_score, 3),
                "matched": True,
            }
        else:
            # ไม่เจอที่คล้ายพอใน taxonomy -> ใช้ชื่อเดิมไปก่อน (ดีกว่าบังคับ map ผิดๆ)
            return {
                "original": raw_skill_name,
                "normalized": raw_skill_name,
                "confidence": round(best_score, 3),
                "matched": False,
            }


# instance เดียวใช้ร่วมกันทั้งโปรแกรม (import แล้วเรียกใช้ได้เลย)
_normalizer = SkillNormalizer()


def normalize_skill_name(raw_skill_name: str) -> dict:
    """ฟังก์ชันสะดวกสำหรับเรียกจากที่อื่น เช่นใน resume_extractor.py / jd_extractor.py"""
    return _normalizer.normalize(raw_skill_name)


def normalize_skill_list(raw_skill_names: list[str]) -> list[dict]:
    """normalize ทีละหลายชื่อพร้อมกัน (ใช้ตอนประมวลผลทั้ง resume หรือ JD)"""
    return [normalize_skill_name(name) for name in raw_skill_names]


# ---------------------------------------------------------
# วิธีเอาไปใช้ใน resume_extractor.py (ตัวอย่าง):
#
#   from skill_normalizer import normalize_skill_name
#
#   result = extract_resume(resume_text)   # ผลจาก LLM เดิม ยังไม่ normalize
#   for skill_item in result.skills:
#       norm = normalize_skill_name(skill_item.skill)
#       skill_item.skill = norm["normalized"]   # แทนที่ชื่อด้วยชื่อมาตรฐาน
#       # ถ้าอยากเก็บไว้ debug ด้วยว่า confidence เท่าไหร่ ก็เก็บแยกไว้ต่างหากได้
#
# ทำแบบเดียวกันใน jd_extractor.py กับ requirements ทุกตัว
# พอทั้ง resume และ JD ผ่านการ normalize ด้วย taxonomy เดียวกันแล้ว
# fit_analyzer.py จะเจอชื่อ skill ที่ "สะกดตรงกัน" มากขึ้นมาก โดยไม่ต้องแก้ fit_analyzer.py เลย
# ---------------------------------------------------------

if __name__ == "__main__":
    # ทดสอบเร็วๆ ว่า normalize ทำงานถูกต้อง
    test_cases = [
        "SOX audits",
        "Sarbanes-Oxley (SOX) compliance",
        "Python programming",
        "python",
        "MS Excel",
        "Microsoft Excel",
    ]
    for name in test_cases:
        result = normalize_skill_name(name)
        print(f"{name!r:40s} -> {result['normalized']!r:40s} (confidence={result['confidence']}, matched={result['matched']})")
