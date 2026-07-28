import json
import os

# Defined exact must_have_count for all 15 pairs
MUST_HAVE_COUNTS = {
    "pair_01": 4,  # total 7 (4 must, 3 nice)
    "pair_02": 4,  # total 7 (4 must, 3 nice)
    "pair_03": 4,  # total 8 (4 must, 4 nice)
    "pair_04": 4,  # total 7 (4 must, 3 nice)
    "pair_05": 4,  # total 7 (4 must, 3 nice)
    "pair_06": 4,  # total 7 (4 must, 3 nice)
    "pair_07": 3,  # total 6 (3 must, 3 nice)
    "pair_08": 4,  # total 7 (4 must, 3 nice)
    "pair_09": 4,  # total 7 (4 must, 3 nice)
    "pair_10": 3,  # total 6 (3 must, 3 nice)
    "pair_11": 3,  # total 6 (3 must, 3 nice)
    "pair_12": 3,  # total 6 (3 must, 3 nice)
    "pair_13": 3,  # total 5 (3 must, 2 nice)
    "pair_14": 3,  # total 5 (3 must, 2 nice)
    "pair_15": 4,  # total 6 (4 must, 2 nice)
}

def calculate_pair_scores(gold_matches, must_count):
    must_matches = gold_matches[:must_count]
    nice_matches = gold_matches[must_count:]

    must_weights = [1.0 if m["status"] == "met" else (0.5 if m["status"] == "partial" else 0.0) for m in must_matches]
    nice_weights = [1.0 if m["status"] == "met" else (0.5 if m["status"] == "partial" else 0.0) for m in nice_matches]

    calc_must = int(sum(must_weights) / len(must_weights) * 100) if must_weights else 0
    calc_nice = int(sum(nice_weights) / len(nice_weights) * 100) if nice_weights else 0

    if must_weights and nice_weights:
        calc_fit = int(0.7 * calc_must + 0.3 * calc_nice)
    elif must_weights:
        calc_fit = calc_must
    else:
        calc_fit = calc_nice

    return calc_must, calc_nice, calc_fit

def main(save=False):
    gold_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gold_dataset_final.json")
    with open(gold_path, 'r', encoding='utf-8') as f:
        dataset = json.load(f)

    print("==========================================================================================")
    print("📊 ตารางเปรียบเทียบ Gold Scores เดิม (JSON) vs คะแนนคำนวณใหม่ตามสูตร 70/30 (Calculated)")
    print("==========================================================================================")
    print(f"{'Pair ID':<10} | {'Role':<32} | {'Must (Old->New)':<16} | {'Nice (Old->New)':<16} | {'Fit (Old->New)':<16}")
    print("------------------------------------------------------------------------------------------")

    updated_dataset = []

    for item in dataset:
        pair_id = item["pair_id"]
        role = item.get("target_role", "Unknown")
        must_count = MUST_HAVE_COUNTS.get(pair_id, 4)

        gold_matches = item.get("gold_matches", [])
        calc_must, calc_nice, calc_fit = calculate_pair_scores(gold_matches, must_count)

        old_must = item.get("gold_must_have_score")
        old_nice = item.get("gold_nice_to_have_score")
        old_fit = item.get("gold_fit_score")

        must_str = f"{old_must} -> {calc_must}"
        nice_str = f"{old_nice} -> {calc_nice}"
        fit_str = f"{old_fit} -> {calc_fit}"

        print(f"{pair_id:<10} | {role[:32]:<32} | {must_str:<16} | {nice_str:<16} | {fit_str:<16}")

        # Update in-memory item
        item["must_have_count"] = must_count
        if save:
            item["gold_must_have_score"] = calc_must
            item["gold_nice_to_have_score"] = calc_nice
            item["gold_fit_score"] = calc_fit

        updated_dataset.append(item)

    print("==========================================================================================")
    if save:
        with open(gold_path, 'w', encoding='utf-8') as f:
            json.dump(updated_dataset, f, indent=2, ensure_ascii=False)
        print("✅ บันทึกข้อมูลลงใน gold_dataset_final.json เรียบร้อยแล้ว")
    else:
        print("ℹ️ โหมดแสดงผลอย่างเดียว (ยังไม่ได้ overwrite ไฟล์จริง) รอคำสั่งยืนยันจากผู้ใช้")

if __name__ == "__main__":
    import sys
    save_flag = "--save" in sys.argv
    main(save=save_flag)
