#!/usr/bin/env python3
"""Run Tableau schema migrations using the app's DATABASE_URL.

Use when alembic upgrade head targets a different database than the running backend.
Run from backend/ with: python scripts/run_pat_migration.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, text
from app.core.config import settings

def main():
    engine = create_engine(settings.DATABASE_URL)
    # Mask URL for logging (hide password)
    mask = settings.DATABASE_URL.split("@")[-1] if "@" in settings.DATABASE_URL else "***"
    print(f"Connecting to ...@{mask}")
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE tableau_server_configs ALTER COLUMN client_id DROP NOT NULL"))
        conn.execute(text("ALTER TABLE tableau_server_configs ALTER COLUMN client_secret DROP NOT NULL"))
        # skip_ssl_verify
        r = conn.execute(text("""
            SELECT EXISTS (SELECT 1 FROM information_schema.columns
            WHERE table_name = 'tableau_server_configs' AND column_name = 'skip_ssl_verify')
        """)).scalar()
        if not r:
            conn.execute(text("ALTER TABLE tableau_server_configs ADD COLUMN skip_ssl_verify BOOLEAN NOT NULL DEFAULT false"))
        conn.commit()
    print("Done: client_id/client_secret nullable, skip_ssl_verify added if missing.")

if __name__ == "__main__":
    main()
