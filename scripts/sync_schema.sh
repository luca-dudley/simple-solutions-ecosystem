#!/usr/bin/env python3
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

target_md = ".ai/SUPABASE_SCHEMA.md"
target_sql = "packages/db/schema.sql"
timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

db_url = None

if os.path.exists(".env"):
    with open(".env", "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("DATABASE_URL="):
                db_url = line.split("DATABASE_URL=", 1)[1].strip()
                if (db_url.startswith('"') and db_url.endswith('"')) or (db_url.startswith("'") and db_url.endswith("'")):
                    db_url = db_url[1:-1]
                break

if not db_url:
    print("❌ Error: DATABASE_URL is not set in your .env file.")
    sys.exit(1)

print("==> [1/3] Connecting directly to Supabase via pg_dump...")
os.makedirs(".ai", exist_ok=True)
os.makedirs("packages/db", exist_ok=True)

try:
    result = subprocess.run(
        ["pg_dump", db_url, "--schema-only", "--schema=public", "--no-owner", "--no-privileges"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    raw_sql = result.stdout
except subprocess.CalledProcessError as e:
    print("❌ pg_dump execution failed:")
    print(e.stderr)
    sys.exit(1)

cleaned_sql = re.sub(r'"x-webhook-secret":"[^"]*"', '"x-webhook-secret":"[REDACTED]"', raw_sql)

with open(target_sql, "w", encoding="utf-8") as f:
    f.write(cleaned_sql)

with open(target_md, "w", encoding="utf-8") as f:
    f.write(f"# Live Supabase Schema Manifest\n")
    f.write(f"> **Last Synchronized:** {timestamp}\n")
    f.write(f"> **Source:** Remote Supabase Instance via pg_dump (Direct Connection)\n")
    f.write(f"> **Single Source of Truth for Autonomous Agents:** @architect, @auditor, @closer\n\n")
    f.write(f"---\n\n## 1. Relational Database Schema & Policies (DDL)\n\n```sql\n")
    f.write(cleaned_sql)
    f.write("\n```\n")

print(f"==> [2/3] Successfully generated {target_sql}")
print(f"==> [3/3] Successfully synced live schema into {target_md}!")
