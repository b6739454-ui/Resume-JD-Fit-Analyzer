import os
import sys
import time
import socket
import ssl
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from google import genai

api_key = os.getenv("GOOGLE_API_KEY")
host = "generativelanguage.googleapis.com"
port = 443

print("=== 1. Low-Level Connection Diagnostic ===")

# Test DNS Resolution
t0 = time.time()
try:
    addresses = socket.getaddrinfo(host, port)
    dns_time = time.time() - t0
    print(f"✅ DNS Resolved in {dns_time:.3f}s:")
    for addr in addresses:
        print(f"   Family: {addr[0].name}, IP: {addr[4][0]}")
except Exception as e:
    print(f"❌ DNS Resolution Failed: {e}")

# Test TCP + SSL Handshake on IPv4 vs IPv6
for family in [socket.AF_INET, socket.AF_INET6]:
    family_name = "IPv4" if family == socket.AF_INET else "IPv6"
    print(f"\n--- Testing Socket ({family_name}) ---")
    t0 = time.time()
    try:
        sock = socket.socket(family, socket.SOCK_STREAM)
        sock.settimeout(5.0)
        sock.connect((host, port))
        connect_time = time.time() - t0
        print(f"✅ TCP Connect ({family_name}) succeeded in {connect_time:.3f}s")
        
        # TLS Handshake
        context = ssl.create_default_context()
        t1 = time.time()
        ssl_sock = context.wrap_socket(sock, server_hostname=host)
        ssl_time = time.time() - t1
        print(f"✅ TLS Handshake ({family_name}) succeeded in {ssl_time:.3f}s")
        ssl_sock.close()
    except Exception as e:
        print(f"❌ Connection ({family_name}) Failed: {type(e).__name__} -> {e}")

print("\n=== 2. Raw Direct google-genai Client Call ===")
t0 = time.time()
try:
    client = genai.Client(api_key=api_key)
    res = client.models.generate_content(
        model="gemini-flash-latest",
        contents="Say 'OK'"
    )
    call_time = time.time() - t0
    print(f"✅ Direct genai.Client call succeeded in {call_time:.3f}s -> Response: {res.text.strip()}")
except Exception as e:
    call_time = time.time() - t0
    print(f"❌ Direct genai.Client call failed after {call_time:.3f}s: {type(e).__name__} -> {e}")
