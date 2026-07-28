import json
import os

def inspect_must_have_counts():
    gold_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gold_dataset_final.json")
    with open(gold_path, 'r', encoding='utf-8') as f:
        dataset = json.load(f)

    print("=== MUST_HAVE_COUNT INSPECTION FOR 15 PAIRS ===")
    for item in dataset:
        pair_id = item["pair_id"]
        role = item.get("target_role", "")
        jd_text = item.get("jd_text", "")
        gold_matches = item.get("gold_matches", [])
        
        # Count bullets in required section vs preferred section
        must_bullets = 0
        nice_bullets = 0
        current = None
        for line in jd_text.splitlines():
            l = line.strip().lower()
            if "required" in l or "must-have" in l:
                current = "must"
                continue
            elif "preferred" in l or "nice-to-have" in l:
                current = "nice"
                continue
            elif any(l.startswith(x) for x in ["we ", "join ", "help "]):
                current = None
                continue
                
            if line.strip().startswith("-"):
                if current == "must":
                    must_bullets += 1
                elif current == "nice":
                    nice_bullets += 1
                    
        print(f"{pair_id} ({role:<40}): matches={len(gold_matches)}, must_bullets={must_bullets}, nice_bullets={nice_bullets}")

if __name__ == "__main__":
    inspect_must_have_counts()
