import os
import sys
import time
import argparse
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

from agents.resume_extractor import extract_resume
from tests.evaluate_gold import call_agent_with_retry

sample_resume = """
John Doe
Software Engineer with 3 years of experience in Python, FastAPI, and PostgreSQL.
Developed RESTful APIs and optimized database queries for web applications.
"""

def main():
    parser = argparse.ArgumentParser(description="Test basic API connectivity")
    parser.add_argument("--api-key-env", type=str, default="GOOGLE_API_KEY", help="Environment variable name for GOOGLE_API_KEY")
    args = parser.parse_args()
    api_key_env = args.api_key_env

    print(f"=== Testing Basic Connectivity (5 Sequential Direct Calls) ===")
    print(f"Model: gemini-flash-latest | API Key Env Var: {api_key_env}\n")
    
    passed_count = 0
    total_runs = 5
    
    for i in range(1, total_runs + 1):
        print(f"Run {i}/{total_runs}: Sending request...", end="", flush=True)
        t0 = time.time()
        try:
            res = call_agent_with_retry(extract_resume, sample_resume, model="gemini-flash-latest", api_key_env_var=api_key_env)
            elapsed = time.time() - t0
            passed_count += 1
            print(f" ✅ PASSED ({elapsed:.2f}s, extracted {len(res.skills)} skills)", flush=True)
        except Exception as e:
            elapsed = time.time() - t0
            print(f" ❌ FAILED ({elapsed:.2f}s): {type(e).__name__} -> {e}", flush=True)
        
        if i < total_runs:
            time.sleep(2)
            
    print(f"\nResult: {passed_count}/{total_runs} PASSED")
    if passed_count == total_runs:
        print("🎉 Network connection is 100% stable and ready for evaluation!")
    else:
        print("⚠️ Network or rate limits are unstable. Do NOT run full evaluation yet.")

if __name__ == "__main__":
    main()
