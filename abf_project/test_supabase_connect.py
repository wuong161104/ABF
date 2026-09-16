import os
import requests
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://azpvcqpnecljsosamnot.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

print(f"Testing secret connection to Supabase URL: {SUPABASE_URL}")
try:
    # Check REST endpoint with secret key
    resp = requests.get(f"{SUPABASE_URL}/rest/v1/", headers={
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    })
    print(f"REST API Response Status: {resp.status_code}")
    print(f"REST API Response snippet: {resp.text[:500]}")
except Exception as e:
    print(f"Error: {e}")
