#!/usr/bin/env python3
"""
Simple Solutions Ecosystem - Cross-Project Storage Migration Pipeline
Path: scripts/pipe_storage_cross_project.py

Pipes storage objects across Supabase projects based on bucket export manifests.
Phase 1: Migrates 'simple_solutions' global catalog from legacy buckets (thumbnails, sops)
into target 'vault-media/global/'.

Usage:
    python3 scripts/pipe_storage_cross_project.py                # Defaults to --dry-run
    python3 scripts/pipe_storage_cross_project.py --execute      # Runs live migration
"""

import os
import sys
import csv
import time
import argparse
import mimetypes
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import requests
except ImportError:
    print("[ERROR] 'requests' library is required. Install via: pip install requests", file=sys.stderr)
    sys.exit(1)

# Default Project Endpoints
DEFAULT_LEGACY_URL = "https://ujhfkvoaaebdntuheyqo.supabase.co"
DEFAULT_TARGET_URL = "https://jlwjqdeffpmabrbwozji.supabase.co"

# Explicit MIME mappings
MIME_OVERRIDES = {
    ".svg": "image/svg+xml",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc": "application/msword",
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".csv": "text/csv",
    ".json": "application/json",
}

# Canonical Slug Normalization Map for filename inconsistencies
CANONICAL_SLUG_MAP = {
    "bush_knives": "bush_knife",
    "high_noise_areas": "farm_noise",
    "general_farm_workers": "general_farm_employees",
    "fertigation_pump_house": "irrigation_pump_house",
}


def load_env_file(filepath: Path) -> Dict[str, str]:
    """Parse local .env file if available for fallback configuration."""
    env_vars = {}
    if filepath.is_file():
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        env_vars[k] = v
        except Exception:
            pass
    return env_vars


def locate_csv_manifest(provided_path: Optional[str]) -> Path:
    """Resolve CSV manifest path from argument or standard repository locations."""
    if provided_path:
        p = Path(provided_path)
        if p.is_file():
            return p
        raise FileNotFoundError(f"Specified CSV manifest not found: {provided_path}")

    search_candidates = [
        Path("data/migration/legacy_bucket_export.csv"),
        Path("legacy/database/Supabase Snippet Full Bucket Export.csv"),
        Path("Supabase Snippet Full Bucket Export.csv"),
        Path("../data/migration/legacy_bucket_export.csv"),
        Path("../legacy/database/Supabase Snippet Full Bucket Export.csv"),
    ]

    for candidate in search_candidates:
        if candidate.is_file():
            return candidate

    raise FileNotFoundError(
        "Could not find 'legacy_bucket_export.csv' or 'Supabase Snippet Full Bucket Export.csv'. Specify via --csv."
    )


def resolve_mime_type(filename: str) -> str:
    """Determine appropriate Content-Type header for storage upload."""
    ext = Path(filename).suffix.lower()
    if ext in MIME_OVERRIDES:
        return MIME_OVERRIDES[ext]
    guessed, _ = mimetypes.guess_type(filename)
    return guessed or "application/octet-stream"


def normalize_slug_and_filename(bucket_id: str, file_name: str) -> Tuple[str, str, str, bool]:
    """
    Extract base slug, apply CANONICAL_SLUG_MAP if present, and output clean canonical target filename.
    Ensures:
      - SOPs adhere to 'sop_{canonical_slug}.docx'
      - Thumbnails adhere to '{canonical_slug}.svg'
    Returns:
      (base_slug, canonical_slug, target_file_name, was_normalized)
    """
    stem = Path(file_name).stem
    ext = Path(file_name).suffix.lower()

    if stem.startswith("sop_"):
        base_slug = stem[4:]
    else:
        base_slug = stem

    canonical_slug = CANONICAL_SLUG_MAP.get(base_slug, base_slug)
    was_normalized = (canonical_slug != base_slug)

    if bucket_id == "sops":
        target_file_name = f"sop_{canonical_slug}.docx"
    elif bucket_id == "thumbnails":
        target_file_name = f"{canonical_slug}.svg"
    else:
        target_file_name = f"{canonical_slug}{ext}"

    return base_slug, canonical_slug, target_file_name, was_normalized


def map_destination_path(bucket_id: str, file_name: str, full_storage_path: str) -> Tuple[str, str, str, bool]:
    """
    Map legacy bucket object to target bucket and canonical path.
    Phase 1 Rule:
      - thumbnails/simple_solutions/* -> vault-media/global/thumbnails/{canonical_slug}.svg
      - sops/simple_solutions/* -> vault-media/global/sops/sop_{canonical_slug}.docx
    Returns:
      (target_bucket, target_path, target_file_name, was_normalized)
    """
    target_bucket = "vault-media"
    base_slug, canonical_slug, target_file_name, was_normalized = normalize_slug_and_filename(bucket_id, file_name)

    if bucket_id == "thumbnails":
        target_path = f"global/thumbnails/{target_file_name}"
    elif bucket_id == "sops":
        target_path = f"global/sops/{target_file_name}"
    else:
        clean_path = full_storage_path.replace("simple_solutions/", "", 1).lstrip("/")
        target_path = f"global/{bucket_id}/{target_file_name}"

    return target_bucket, target_path, target_file_name, was_normalized


def build_legacy_download_urls(
    legacy_url: str,
    bucket_id: str,
    storage_path: str
) -> List[str]:
    """
    Construct URLs to fetch object from legacy Supabase storage.
    Tries authenticated object endpoint, then public object endpoint.
    """
    base = legacy_url.rstrip("/")
    clean_path = storage_path.lstrip("/")
    return [
        f"{base}/storage/v1/object/authenticated/{bucket_id}/{clean_path}",
        f"{base}/storage/v1/object/{bucket_id}/{clean_path}",
        f"{base}/storage/v1/object/public/{bucket_id}/{clean_path}",
    ]


def verify_legacy_object(
    legacy_urls: List[str],
    headers: Dict[str, str]
) -> Tuple[bool, int, Optional[str], Optional[int]]:
    """Test accessibility of object on legacy Supabase storage."""
    for url in legacy_urls:
        try:
            resp = requests.head(url, headers=headers, timeout=10, allow_redirects=True)
            if resp.status_code == 200:
                length = resp.headers.get("Content-Length")
                size = int(length) if length and length.isdigit() else None
                return True, 200, url, size
            if resp.status_code == 404:
                continue
            # Some servers reject HEAD, try Range GET
            resp_get = requests.get(url, headers={**headers, "Range": "bytes=0-0"}, timeout=10)
            if resp_get.status_code in (200, 206):
                return True, resp_get.status_code, url, None
        except Exception:
            continue
    return False, 404, None, None


def transfer_object(
    legacy_urls: List[str],
    legacy_headers: Dict[str, str],
    target_upload_url: str,
    target_headers: Dict[str, str]
) -> Tuple[bool, int, str]:
    """Stream object from legacy Supabase and upload directly into target Supabase bucket."""
    last_status = 0
    last_error = ""

    for download_url in legacy_urls:
        try:
            with requests.get(download_url, headers=legacy_headers, stream=True, timeout=60) as resp_get:
                last_status = resp_get.status_code
                if resp_get.status_code not in (200, 206):
                    last_error = f"Legacy download failed with HTTP {resp_get.status_code}"
                    continue

                content = resp_get.content
                file_size = len(content)

                # Direct upload to target storage
                resp_post = requests.post(
                    target_upload_url,
                    headers=target_headers,
                    data=content,
                    timeout=90
                )

                if resp_post.status_code in (200, 201):
                    return True, resp_post.status_code, f"{file_size:,} bytes"
                else:
                    return False, resp_post.status_code, resp_post.text or "Target upload rejected"

        except Exception as exc:
            last_error = str(exc)
            continue

    return False, last_status or 500, last_error or "Unable to download from legacy source"


def main():
    parser = argparse.ArgumentParser(
        description="Cross-project Supabase storage migration pipeline (Phase 1: Global Master Catalog)."
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        default=False,
        help="Execute the live storage migration. Default is dry-run mode."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Perform dry-run inspection without writing files (default behavior)."
    )
    parser.add_argument(
        "--csv",
        type=str,
        default=None,
        help="Path to 'Supabase Snippet Full Bucket Export.csv'."
    )
    parser.add_argument(
        "--folder",
        type=str,
        default="simple_solutions",
        help="Filter folder in CSV (default: 'simple_solutions')."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional limit on number of files to process."
    )
    parser.add_argument(
        "--legacy-url",
        type=str,
        default=None,
        help="Legacy Supabase URL (overrides LEGACY_SUPABASE_URL)."
    )
    parser.add_argument(
        "--legacy-key",
        type=str,
        default=None,
        help="Legacy Supabase Service Role Key (overrides LEGACY_SERVICE_ROLE_KEY)."
    )
    parser.add_argument(
        "--target-url",
        type=str,
        default=None,
        help="Target Supabase URL (overrides TARGET_SUPABASE_URL)."
    )
    parser.add_argument(
        "--target-key",
        type=str,
        default=None,
        help="Target Supabase Service Role Key (overrides SERVICE_ROLE_KEY or TARGET_SERVICE_ROLE_KEY)."
    )

    args = parser.parse_args()

    # Determine execution mode (dry-run by default unless --execute is explicitly specified)
    is_dry_run = not args.execute or args.dry_run

    # Load environment variables (from environment or .env fallback)
    local_env = load_env_file(Path(".env"))
    
    legacy_url = (
        args.legacy_url
        or os.environ.get("LEGACY_SUPABASE_URL")
        or local_env.get("LEGACY_SUPABASE_URL")
        or os.environ.get("SUPABASE_URL")
        or DEFAULT_LEGACY_URL
    ).rstrip("/")

    legacy_key = (
        args.legacy_key
        or os.environ.get("LEGACY_SERVICE_ROLE_KEY")
        or local_env.get("LEGACY_SERVICE_ROLE_KEY")
        or ""
    )

    target_url = (
        args.target_url
        or os.environ.get("TARGET_SUPABASE_URL")
        or local_env.get("TARGET_SUPABASE_URL")
        or DEFAULT_TARGET_URL
    ).rstrip("/")

    target_key = (
        args.target_key
        or os.environ.get("SERVICE_ROLE_KEY")
        or os.environ.get("TARGET_SERVICE_ROLE_KEY")
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        or local_env.get("SERVICE_ROLE_KEY")
        or local_env.get("TARGET_SERVICE_ROLE_KEY")
        or local_env.get("SUPABASE_SERVICE_ROLE_KEY")
        or ""
    )

    # Validate execution mode security requirements
    if not is_dry_run and not target_key:
        print(
            "\n[SECURITY ERROR] SERVICE_ROLE_KEY (or TARGET_SERVICE_ROLE_KEY) is required to execute storage upload.\n"
            "Set SERVICE_ROLE_KEY in your .env or environment, or pass via --target-key.\n",
            file=sys.stderr
        )
        sys.exit(1)

    # Locate and read manifest
    try:
        csv_file = locate_csv_manifest(args.csv)
    except FileNotFoundError as err:
        print(f"\n[ERROR] {err}", file=sys.stderr)
        sys.exit(1)

    print("=" * 80)
    print("  SIMPLE SOLUTIONS ECOSYSTEM: CROSS-PROJECT STORAGE PIPELINE")
    print("  Phase 1: Global Master Catalog ('simple_solutions' -> 'vault-media/global/')")
    print("=" * 80)
    print(f"  Mode:                {'[DRY-RUN] (No writes performed)' if is_dry_run else '[LIVE EXECUTE]'}")
    print(f"  Manifest CSV:        {csv_file}")
    print(f"  Folder Filter:       {args.folder}")
    print(f"  Legacy Source:       {legacy_url}")
    print(f"  Target Destination:  {target_url}")
    print(f"  Legacy Auth:         {'Provided (Bearer token)' if legacy_key else 'Anonymous / Public'}")
    print(f"  Target Auth:         {'Configured (Service Key)' if target_key else 'Not supplied'}")
    print("-" * 80)

    # Read and filter records
    records = []
    with open(csv_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("folder") == args.folder:
                records.append(row)

    if args.limit:
        records = records[:args.limit]

    total_records = len(records)
    print(f"Found {total_records} files matching folder='{args.folder}'.")
    if total_records == 0:
        print("[INFO] No files to process. Exiting.")
        sys.exit(0)

    print("\nBeginning transfer stream:\n")

    # Set up request headers
    legacy_headers = {
        "User-Agent": "SimpleSolutions-StoragePipe/1.0",
    }
    if legacy_key:
        legacy_headers["Authorization"] = f"Bearer {legacy_key}"
        legacy_headers["apikey"] = legacy_key

    # Stats tracking
    stats = {
        "migrated": 0,
        "verified": 0,
        "skipped": 0,
        "failed": 0,
        "normalized": 0,
        "total_bytes": 0,
    }

    start_time = time.time()

    for idx, row in enumerate(records, start=1):
        bucket_id = row.get("bucket_id", "").strip()
        file_name = row.get("file_name", "").strip()
        full_storage_path = row.get("full_storage_path", "").strip()

        if not bucket_id or not full_storage_path or not file_name:
            print(f"[{idx}/{total_records}] [SKIP] Malformed CSV row: {row}")
            stats["skipped"] += 1
            continue

        target_bucket, dest_path, target_file_name, was_normalized = map_destination_path(
            bucket_id, file_name, full_storage_path
        )
        if was_normalized:
            stats["normalized"] += 1

        mime_type = resolve_mime_type(target_file_name)

        legacy_urls = build_legacy_download_urls(legacy_url, bucket_id, full_storage_path)
        target_upload_url = f"{target_url}/storage/v1/object/{target_bucket}/{dest_path}"

        target_headers = {
            "Authorization": f"Bearer {target_key}",
            "apikey": target_key,
            "Content-Type": mime_type,
            "x-upsert": "true",
            "User-Agent": "SimpleSolutions-StoragePipe/1.0",
        }

        prefix = f"[{idx:02d}/{total_records:02d}]"
        norm_str = f" [SLUG NORMALIZED: {file_name} -> {target_file_name}]" if was_normalized else ""

        if is_dry_run:
            # Verify source presence on legacy project
            found, status_code, valid_url, size = verify_legacy_object(legacy_urls, legacy_headers)
            size_str = f" ({size:,} bytes)" if size else ""
            if found:
                stats["verified"] += 1
                stats["migrated"] += 1
                print(f"{prefix} [DRY-RUN {status_code} OK] {bucket_id}/{full_storage_path} -> {target_bucket}/{dest_path}{norm_str}{size_str}")
            else:
                stats["failed"] += 1
                print(f"{prefix} [DRY-RUN {status_code} FAIL] Source not found: {bucket_id}/{full_storage_path}")
        else:
            # Live pipe streaming
            success, status_code, message = transfer_object(
                legacy_urls,
                legacy_headers,
                target_upload_url,
                target_headers
            )

            if success:
                stats["migrated"] += 1
                print(f"{prefix} [{status_code} OK] Migrated: {bucket_id}/{full_storage_path} -> {target_bucket}/{dest_path}{norm_str} ({message})")
            else:
                stats["failed"] += 1
                print(f"{prefix} [{status_code} FAIL] Failed: {bucket_id}/{full_storage_path} -> {target_bucket}/{dest_path}{norm_str} (Error: {message})")

    elapsed = time.time() - start_time

    # Verification Report
    print("\n" + "=" * 80)
    print("  EXECUTION VERIFICATION REPORT")
    print("=" * 80)
    print(f"  Status Mode:       {'DRY RUN (Simulated)' if is_dry_run else 'EXECUTED (Live Migration)'}")
    print(f"  Total Filtered:    {total_records}")
    if is_dry_run:
        print(f"  Verified Sources:  {stats['verified']}")
        print(f"  Planned Transfers: {stats['migrated']}")
    else:
        print(f"  Total Migrated:    {stats['migrated']}")
    print(f"  Normalized Slugs:  {stats['normalized']}")
    print(f"  Total Skipped:     {stats['skipped']}")
    print(f"  Total Failed:      {stats['failed']}")
    print(f"  Duration:          {elapsed:.2f} seconds")
    print("=" * 80)

    if is_dry_run:
        print("\n[NOTE] Dry-run complete. To execute real transfer, pass: --execute")
        print("Ensure SERVICE_ROLE_KEY is set in your .env or environment before executing.\n")

    sys.exit(1 if stats["failed"] > 0 and not is_dry_run else 0)


if __name__ == "__main__":
    main()
