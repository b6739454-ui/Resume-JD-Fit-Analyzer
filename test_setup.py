from dotenv import load_dotenv
import os
from google import genai

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    print("❌ ไม่เจอ GOOGLE_API_KEY ใน .env — เช็คไฟล์อีกที")
else:
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model="gemini-flash-latest",
        contents="พูดว่า setup สำเร็จ"
    )
    print("✅", response.text)