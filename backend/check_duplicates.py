import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/tableau_demo")

engine = create_engine(DATABASE_URL)
with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT server_url, COUNT(*) as count, array_agg(id) as ids, array_agg(name) as names
        FROM tableau_server_configs
        GROUP BY server_url
        HAVING COUNT(*) > 1
    """))
    duplicates = result.fetchall()
    if duplicates:
        print("Found duplicate server URLs:")
        for row in duplicates:
            print(f"  {row[0]}: {row[1]} configs (IDs: {row[2]}, Names: {row[3]})")
        sys.exit(1)
    else:
        print("No duplicate server URLs found. Safe to run migration.")
        sys.exit(0)
