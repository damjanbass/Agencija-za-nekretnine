import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

EMAIL_FROM      = os.getenv("EMAIL_FROM", os.getenv("SMTP_USER", ""))
EMAIL_FROM_NAME = os.getenv("EMAIL_FROM_NAME", "Nekretnine Izveštaji")
SUPPORT_EMAIL   = os.getenv("SUPPORT_EMAIL", EMAIL_FROM)

CLAUDE_MODEL = "claude-sonnet-4-6"
CLAUDE_AGENT_MODEL = "claude-haiku-4-5"

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://cesxmcbodcpfnpyusxhj.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

# Proxy za scraping — opciono. Jedan URL ili comma-separated lista za rotaciju.
# Format: http://user:pass@host:port  ili  socks5://user:pass@host:port
# Primer Bright Data: http://lum-customer-XXX-zone-residential:pass@zproxy.lum-superproxy.io:22225
# Primer Smartproxy:  http://user:pass@gate.smartproxy.com:7000
SCRAPER_PROXIES = [
    p.strip()
    for p in os.getenv("SCRAPER_PROXIES", "").split(",")
    if p.strip()
]
