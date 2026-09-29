#!/usr/bin/env bash
set -e
SCHEMA_FILE=".ai/SUPABASE_SCHEMA.md"
TMP_SCHEMA="/tmp/ecosystem_live_schema.sql"

echo "[INFO] Checking Supabase schema synchronization..."
if npx --yes supabase db dump --schema-only -f "$TMP_SCHEMA" >/dev/null 2>&1; then
    cat << 'HEADER' > "$SCHEMA_FILE"
# The Ecosystem: Master Supabase Schema
> Auto-generated via Supabase CLI. Do not manually edit.

HEADER
    cat "$TMP_SCHEMA" >> "$SCHEMA_FILE"
    rm -f "$TMP_SCHEMA"
    echo "[SUCCESS] Updated $SCHEMA_FILE from remote instance."
else
    echo "[WARN] Supabase CLI not linked or offline. Preserving local schema definitions."
fi
