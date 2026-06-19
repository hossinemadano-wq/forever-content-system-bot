import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

supabase = create_client(url, key)

response = supabase.table("app_users").select("*").limit(1).execute()

print("Supabase connection OK")
print(response.data)