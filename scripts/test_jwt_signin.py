#!/usr/bin/env python3
"""Generate a test JWT and curl command for Tableau sign-in. Run from project root."""
import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

# Load .env before importing app (which uses settings)
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from app.services.eas_jwt_builder import build_tableau_jwt

ISSUER = os.getenv("BACKEND_API_URL", "https://8d3a-165-225-243-14.ngrok-free.app").rstrip("/")
SUB = os.getenv("TEST_JWT_SUB", "albertcwong@gmail.com")
KEY_PATH = os.getenv("EAS_JWT_KEY_PATH", "credentials/eas_jwt_key.pem")
TABLEAU_URL = os.getenv("TABLEAU_SERVER_URL", "https://ec2-34-209-90-187.us-west-2.compute.amazonaws.com")
SITE = os.getenv("TABLEAU_SITE_ID", "")
AUD = "tableau"  # Server-wide EAS; for site-level use tableau:<site_luid>

if __name__ == "__main__":
    # Key path is relative to backend/ when running from project root
    key_path = Path(__file__).parent.parent / "backend" / KEY_PATH
    token = build_tableau_jwt(issuer=ISSUER, sub=SUB, key_path=str(key_path), aud=AUD)
    if not token:
        print("Failed to build JWT. Check EAS_JWT_KEY_PATH.", file=sys.stderr)
        sys.exit(1)
    print("# JWT payload: iss=%s sub=%s aud=%s" % (ISSUER, SUB, AUD))
    print("# Decode at https://jwt.io")
    print()
    cmd = f'curl -X POST "{TABLEAU_URL}/api/3.27/auth/signin" \\\n  -H "Content-Type: application/json" \\\n  -d \'{{"credentials":{{"jwt":"{token}","site":{{"contentUrl":"{SITE}"}}}}}}\''
    print(cmd)
