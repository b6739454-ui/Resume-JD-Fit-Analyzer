import json

with open('tests/evaluation_progress.json', encoding='utf-8') as f:
    data = json.load(f)

results = data['results']
print(f'Pairs completed: {len(results)}/15\n')
print(f"{'Pair ID':<10} | {'Gold Must':>9} | {'Py Must':>7} | {'Gold Nice':>9} | {'Py Nice':>7} | {'Gold Fit':>8} | {'Py Fit':>6}")
print('-' * 72)
for r in results:
    print(f"{r['pair_id']:<10} | {r['gold_must']:>9} | {r['pred_py_must']:>7} | {r['gold_nice']:>9} | {r['pred_py_nice']:>7} | {r['gold_fit']:>8} | {r['pred_py_fit']:>6}")

mh_c = data.get('must_have_correct', 0)
mh_t = data.get('must_have_total', 0)
nth_c = data.get('nice_to_have_correct', 0)
nth_t = data.get('nice_to_have_total', 0)
uc = data.get('unsupported_claims_count', 0)
tc = data.get('total_claims_count', 0)

print()
if mh_t:
    print(f'Must-Have Accuracy    ({len(results)} pairs): {mh_c}/{mh_t} = {mh_c/mh_t*100:.1f}%')
if nth_t:
    print(f'Nice-To-Have Accuracy ({len(results)} pairs): {nth_c}/{nth_t} = {nth_c/nth_t*100:.1f}%')
if tc:
    print(f'Unsupported Claims    ({len(results)} pairs): {uc}/{tc} = {uc/tc*100:.1f}%')
