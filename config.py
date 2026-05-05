import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

EMAIL_FROM      = "izvestaji@vasaagencija.rs"
EMAIL_FROM_NAME = "Nekretnine Izveštaji"

CLAUDE_MODEL = "claude-sonnet-4-6"

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://cesxmcbodcpfnpyusxhj.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
