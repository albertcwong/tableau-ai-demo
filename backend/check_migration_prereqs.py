#!/usr/bin/env python3
"""Check prerequisites before running migration ae_add_unique_server_url_and_ssl_cert_path."""
import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import create_engine, text
from app.core.config import settings

def check_duplicates():
    """Check for duplicate server URLs."""
    engine = create_engine(settings.DATABASE_URL)
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT server_url, COUNT(*) as count, array_agg(id ORDER BY id) as ids, array_agg(name ORDER BY id) as names
            FROM tableau_server_configs
            GROUP BY server_url
            HAVING COUNT(*) > 1
        """))
        duplicates = result.fetchall()
        if duplicates:
            print("❌ Found duplicate server URLs:")
            print()
            for row in duplicates:
                print(f"  Server URL: {row[0]}")
                print(f"    Count: {row[1]} configurations")
                print(f"    IDs: {row[2]}")
                print(f"    Names: {row[3]}")
                print()
            print("⚠️  Please resolve duplicates before running migration.")
            print("   You can:")
            print("   1. Delete duplicate configurations via admin UI")
            print("   2. Or manually update/delete duplicates in the database")
            return False
        else:
            print("✅ No duplicate server URLs found. Safe to run migration.")
            return True

if __name__ == "__main__":
    try:
        if check_duplicates():
            sys.exit(0)
        else:
            sys.exit(1)
    except Exception as e:
        print(f"❌ Error checking prerequisites: {e}")
        sys.exit(1)
