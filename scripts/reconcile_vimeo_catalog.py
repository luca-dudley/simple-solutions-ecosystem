#!/usr/bin/env python3
"""
Simple Solutions Ecosystem - Vimeo Catalog Reconciler & Batch-Renaming Tool
Path: scripts/reconcile_vimeo_catalog.py

Reconciles existing Vimeo video titles against canonical module slugs:
1. Inputs:
   - Reads 'data/migration/vimeo_catalog_audit.csv' (from scripts/audit_vimeo_catalog.py)
   - Reads canonical slugs from 'data/migration/legacy_bucket_export.csv' using CANONICAL_SLUG_MAP
2. Reconciliation Logic:
   - Maps folder context to scope: Simple_Branded -> 'global', {Tenant}_Farm_Branded -> '{tenant}'
   - Detects language flags in title (e.g., 'Zulu', 'isizulu', 'Afrikaans' -> 'zu', 'af', default 'en')
   - Matches closest canonical slug (exact, alias, and fuzzy sequence matching)
   - Formulates proposed standardized title: "{slug}__{lang}__{tenant_or_global} - {Clean Title}"
3. Execution Modes:
   - Mode 1: Dry-run reconciliation (--plan) -> outputs 'data/migration/vimeo_rename_plan.csv'
   - Mode 2: Batch API update (--apply) -> issues PATCH requests to https://api.vimeo.com/videos/{vimeo_id}
"""

import os
import sys
import csv
import time
import json
import re
import difflib
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any

# Try importing requests; fallback to urllib
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    import urllib.request
    import urllib.error
    import urllib.parse

# Default Paths
DEFAULT_AUDIT_CSV = "data/migration/vimeo_catalog_audit.csv"
DEFAULT_LEGACY_CSV = "data/migration/legacy_bucket_export.csv"
DEFAULT_PLAN_CSV = "data/migration/vimeo_rename_plan.csv"
VIMEO_API_BASE = "https://api.vimeo.com"

# Canonical Slug Normalization Map for filename inconsistencies (from scripts/pipe_storage_cross_project.py)
CANONICAL_SLUG_MAP: Dict[str, str] = {
    "bush_knives": "bush_knife",
    "high_noise_areas": "farm_noise",
    "general_farm_workers": "general_farm_employees",
    "fertigation_pump_house": "irrigation_pump_house",
}

# Known direct aliases and phrase variations mapping to canonical slugs
SLUG_ALIASES: Dict[str, List[str]] = {
    "angle_grinder": ["angle grinder", "angle grinder safety"],
    "banana_desuckering": ["banana desuckering"],
    "banana_fertilizer_application": ["banana fertilizer", "banana fertilizer application"],
    "banana_planting": ["banana planting"],
    "banana_propping": ["banana propping"],
    "band_prop_saw": ["band prop saw", "band prop saw safety", "bandpop saw", "bandpop saw safety"],
    "brush_cutter": ["brush cutter", "brush cutter safety"],
    "bush_knife": ["bush knife", "bush knife safety", "bush knives"],
    "chainsaw": ["chainsaw", "chainsaw safety"],
    "citrus_chemical_spraying": ["citrus chemical spraying"],
    "citrus_orchard": ["citrus orchard", "citrus orchard safety"],
    "citrus_orchard_harvest": ["citrus orchard harvest"],
    "citrus_orchard_hygiene": ["citrus orchard hygiene"],
    "citrus_orchard_ladder": ["citrus orchard ladder", "citrus orchard ladder safety"],
    "electrical_hazards": ["electrical hazards", "electricity hazards"],
    "employee_allergens": ["employee allergens"],
    "farm_noise": ["farm noise", "farm noise exposure safety", "farm noise exposure", "high noise areas"],
    "farm_saw": ["farm saw", "farm saw safety"],
    "general_farm_employees": ["general farm employees", "general staff safety", "general farm staff safety", "general farm workers"],
    "hygiene": ["hygiene"],
    "irrigation_manager": ["irrigation manager"],
    "irrigation_pump_house": ["irrigation pump house", "irrigation pump house safety", "fertigation pump house", "fertigation pump house safety"],
    "macadamia_boiler": ["mac boiler", "boiler", "macadamia boiler"],
    "macadamia_chemical_spraying": ["spray training safety", "macadamia chemical spraying"],
    "macadamia_dehusking": ["mac dehusking", "dehusking", "macadamia dehusking"],
    "macadamia_drying": ["mac drying", "drying", "macadamia drying"],
    "macadamia_harvesting": ["macadamia harvesting"],
    "macadamia_sorting": ["macadamia sorting"],
    "macadamia_storage": ["mac storage", "storage", "macadamia storage"],
    "oxy_acetylene": ["oxy acetylene", "oxy acetylene safety"],
    "senior_farm_manager": ["senior farm manager"],
    "tractor_logbook": ["tractor logbook"],
    "tractor_operation": ["tractor operation"],
    "tractor_operator": ["tractor operator"],
    "welding": ["welding", "welding safety"],
    "workshop_manager": ["workshop manager"],
}


def load_env_file(filepath: Path) -> Dict[str, str]:
    """Parse local .env file if available for fallback configuration."""
    env_vars: Dict[str, str] = {}
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
        except Exception as err:
            print(f"[WARN] Failed to read {filepath}: {err}", file=sys.stderr)
    return env_vars


def resolve_vimeo_token(cli_token: Optional[str]) -> str:
    """Resolve Vimeo API access token from CLI args, environment, or .env files."""
    if cli_token:
        return cli_token.strip()

    if "VIMEO_ACCESS_TOKEN" in os.environ and os.environ["VIMEO_ACCESS_TOKEN"].strip():
        return os.environ["VIMEO_ACCESS_TOKEN"].strip()

    search_candidates = [
        Path(".env"),
        Path("../.env"),
        Path("../../.env"),
        Path(".env.local"),
    ]

    for candidate in search_candidates:
        if candidate.is_file():
            loaded = load_env_file(candidate)
            if "VIMEO_ACCESS_TOKEN" in loaded and loaded["VIMEO_ACCESS_TOKEN"].strip():
                return loaded["VIMEO_ACCESS_TOKEN"].strip()

    print("[ERROR] VIMEO_ACCESS_TOKEN not found in environment, .env, or CLI argument.", file=sys.stderr)
    print("Please set VIMEO_ACCESS_TOKEN in .env or run with: --token <YOUR_TOKEN>", file=sys.stderr)
    sys.exit(1)


def load_canonical_slugs(legacy_csv_path: str) -> Set[str]:
    """Extract canonical module slugs from legacy bucket export manifest."""
    csv_file = Path(legacy_csv_path)
    if not csv_file.is_file():
        raise FileNotFoundError(f"Legacy bucket export CSV not found at: {legacy_csv_path}")

    slugs: Set[str] = set()
    with open(csv_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            filename = row.get("file_name", "")
            stem = Path(filename).stem
            if stem.startswith("sop_"):
                base_slug = stem[4:]
            else:
                base_slug = stem

            canonical_slug = CANONICAL_SLUG_MAP.get(base_slug, base_slug)
            if canonical_slug:
                slugs.add(canonical_slug)

    return slugs


def extract_folder_scope(folder_name: str) -> str:
    """
    Extract tenant scope or 'global' from folder context.
    e.g.:
      Simple_Branded -> 'global'
      Doveton_Farm_Branded -> 'doveton'
      Elliott_Farm_Branded -> 'elliott'
      Outlook_Farm_Branded -> 'outlook'
      TGK_Farm_Branded -> 'tgk'
      Landing_Page -> 'landing_page'
    """
    if not folder_name:
        return "unassigned"

    if folder_name.lower() in ("simple_branded", "simple_solutions", "global"):
        return "global"

    match = re.match(r"^(.*)_Farm_Branded$", folder_name, flags=re.IGNORECASE)
    if match:
        return match.group(1).lower()

    match_branded = re.match(r"^(.*)_Branded$", folder_name, flags=re.IGNORECASE)
    if match_branded:
        return match_branded.group(1).lower()

    return folder_name.lower().replace(" ", "_")


def detect_language(title: str) -> str:
    """
    Detect language code from title flags.
    Defaults to 'en' (English).
    Supported: 'zu' (Zulu/isiZulu), 'af' (Afrikaans), 'xh' (Xhosa), 'st' (Sotho).
    """
    if re.search(r"\b(zulu|isizulu|zul)\b", title, flags=re.IGNORECASE):
        return "zu"
    if re.search(r"\b(afrikaans|afr)\b", title, flags=re.IGNORECASE):
        return "af"
    if re.search(r"\b(xhosa|isixhosa)\b", title, flags=re.IGNORECASE):
        return "xh"
    if re.search(r"\b(sotho|sesotho)\b", title, flags=re.IGNORECASE):
        return "st"
    return "en"


def clean_title(title: str, folder_name: str) -> str:
    """
    Strip boilerplate prefixes, suffixes, file extensions, and brand tags.
    Preserves module descriptor and variant flags (e.g. EA).
    """
    t = title.strip()
    # Remove leading company prefixes (e.g. 'Simple.za - ', 'Simple - ')
    t = re.sub(r"^(Simple\.za\s*-\s*|Simple\s*-\s*)", "", t, flags=re.IGNORECASE).strip()
    # Remove trailing extension if present (.mp4, .mov, etc.)
    t = re.sub(r"\.(mp4|mov|avi|mkv)$", "", t, flags=re.IGNORECASE).strip()
    # Remove tenant suffix (e.g. '_Doveton', '_Elliott', '_Outlook', '_TGK')
    t = re.sub(r"_(Doveton|Elliott|Outlook|TGK)$", "", t, flags=re.IGNORECASE).strip()
    return t


def match_canonical_slug(cleaned_title: str, canonical_slugs: Set[str]) -> Tuple[str, float, str]:
    """
    Match cleaned title against canonical slugs and known aliases.
    Returns:
      (matched_slug, confidence_score, match_type)
      where confidence_score is:
        1.0 for exact alias or direct slug match
        0.85-0.95 for strong phrase/alias overlap
        0.75-0.84 for sequence fuzzy match
        0.0 for unmapped
    """
    norm = re.sub(r"[^a-z0-9 ]", " ", cleaned_title.lower()).strip()
    norm = re.sub(r"\s+", " ", norm)

    if not norm:
        return "", 0.0, "unmapped"

    # 1. Exact alias match
    for slug, aliases in SLUG_ALIASES.items():
        for alias in aliases:
            if norm == alias:
                return slug, 1.0, "exact_alias"

    # 2. Exact match against canonical slug directly (with underscores to spaces)
    slug_as_phrase = norm.replace(" ", "_")
    if slug_as_phrase in canonical_slugs:
        return slug_as_phrase, 1.0, "exact_slug"

    # 3. Known alias substring/boundary match (e.g. 'Hygiene EA' -> contains 'hygiene')
    for slug, aliases in SLUG_ALIASES.items():
        for alias in aliases:
            pattern = rf"(^|\s){re.escape(alias)}(\s|$)"
            if re.search(pattern, norm):
                return slug, 0.95, "fuzzy_alias"

    # 4. Fuzzy SequenceMatcher comparison against all canonical slugs & aliases
    best_slug = ""
    best_score = 0.0
    for slug in canonical_slugs:
        aliases = SLUG_ALIASES.get(slug, [slug.replace("_", " ")])
        for alias in aliases:
            ratio = difflib.SequenceMatcher(None, norm, alias).ratio()
            if ratio > best_score:
                best_score = ratio
                best_slug = slug

    if best_score >= 0.75:
        return best_slug, round(best_score, 2), "fuzzy_seq"

    return "", 0.0, "unmapped"


def generate_plan(audit_csv: str, legacy_csv: str, plan_csv: str) -> None:
    """Generate reconciliation rename plan CSV without modifying Vimeo."""
    print("=" * 64)
    print("Vimeo Catalog Reconciler - Plan Generation (Dry-Run)")
    print("=" * 64)

    canonical_slugs = load_canonical_slugs(legacy_csv)
    print(f"[1/3] Loaded {len(canonical_slugs)} canonical slugs from '{legacy_csv}'.")

    audit_path = Path(audit_csv)
    if not audit_path.is_file():
        raise FileNotFoundError(f"Vimeo audit CSV not found at: {audit_csv}. Run scripts/audit_vimeo_catalog.py first.")

    with open(audit_path, "r", encoding="utf-8") as f:
        records = list(csv.DictReader(f))

    print(f"[2/3] Analyzing {len(records)} videos from '{audit_csv}'...")

    plan_rows: List[Dict[str, Any]] = []
    exact_count = 0
    fuzzy_count = 0
    unmapped_count = 0

    lang_stats: Dict[str, int] = {}
    scope_stats: Dict[str, int] = {}

    for row in records:
        vimeo_id = row.get("vimeo_id", "").strip()
        folder_name = row.get("folder_name", "").strip()
        current_title = row.get("title", "").strip()

        cleaned = clean_title(current_title, folder_name)
        scope = extract_folder_scope(folder_name)
        lang = detect_language(current_title)

        matched_slug, confidence, match_type = match_canonical_slug(cleaned, canonical_slugs)

        if confidence == 1.0:
            exact_count += 1
            proposed_title = f"{matched_slug}__{lang}__{scope} - {cleaned}"
        elif confidence > 0.0:
            fuzzy_count += 1
            proposed_title = f"{matched_slug}__{lang}__{scope} - {cleaned}"
        else:
            unmapped_count += 1
            proposed_title = ""  # Left blank to prevent accidental renaming of marketing/draft videos

        lang_stats[lang] = lang_stats.get(lang, 0) + 1
        scope_stats[scope] = scope_stats.get(scope, 0) + 1

        plan_rows.append({
            "vimeo_id": vimeo_id,
            "folder_name": folder_name,
            "current_title": current_title,
            "matched_slug": matched_slug,
            "detected_lang": lang,
            "scope": scope,
            "proposed_title": proposed_title,
            "confidence_score": f"{confidence:.2f}",
        })

    # Save to plan CSV
    out_plan = Path(plan_csv)
    out_plan.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "vimeo_id",
        "folder_name",
        "current_title",
        "matched_slug",
        "detected_lang",
        "scope",
        "proposed_title",
        "confidence_score",
    ]

    with open(out_plan, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in plan_rows:
            writer.writerow(r)

    print(f"[3/3] Successfully generated plan with {len(plan_rows)} entries.")

    # Summary Statistics
    print("\n" + "=" * 64)
    print("VIMEO CATALOG RECONCILIATION SUMMARY")
    print("=" * 64)
    print(f"Total videos analyzed:        {len(plan_rows):>4}")
    print(f"Exact slug matches (1.00):    {exact_count:>4}")
    print(f"Fuzzy slug matches (< 1.00):  {fuzzy_count:>4}")
    print(f"Unmapped / draft videos:      {unmapped_count:>4}")
    print("=" * 64)
    print("Language Breakdown:")
    for l_code, count in sorted(lang_stats.items()):
        print(f"  * {l_code:<12} : {count:>4} videos")
    print("\nScope / Tenant Breakdown:")
    for sc, count in sorted(scope_stats.items()):
        print(f"  * {sc:<12} : {count:>4} videos")
    print("=" * 64)
    print(f"Reconciliation plan exported to: {out_plan.resolve()}")
    print("To execute updates on Vimeo, review the plan and run:")
    print(f"  python3 scripts/reconcile_vimeo_catalog.py --apply")
    print("=" * 64)


def apply_renames(plan_csv: str, token: str, dry_run: bool = False, min_confidence: float = 0.7) -> None:
    """Read reconciliation plan CSV and batch-update video names via Vimeo PATCH API."""
    print("=" * 64)
    print(f"Vimeo Batch Renamer - {'DRY RUN' if dry_run else 'LIVE EXECUTION'}")
    print("=" * 64)

    plan_path = Path(plan_csv)
    if not plan_path.is_file():
        raise FileNotFoundError(f"Plan CSV not found at: {plan_csv}. Run with --plan first.")

    with open(plan_path, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.vimeo.*+json;version=3.4",
        "Content-Type": "application/json",
        "User-Agent": "SimpleSolutions-VimeoRenamer/1.0",
    }

    if HAS_REQUESTS:
        session = requests.Session()
        session.headers.update(headers)

    total = len(rows)
    updated = 0
    skipped = 0
    failed = 0

    print(f"Processing {total} catalog entries from '{plan_csv}'...\n")

    for idx, row in enumerate(rows, start=1):
        vimeo_id = row.get("vimeo_id", "").strip()
        current_title = row.get("current_title", "").strip()
        proposed_title = row.get("proposed_title", "").strip()
        conf = float(row.get("confidence_score") or 0.0)

        # Skip unmapped or low-confidence entries
        if not proposed_title:
            print(f"[{idx:>3}/{total}] [SKIP] #{vimeo_id} ('{current_title}'): No proposed title.")
            skipped += 1
            continue

        if conf < min_confidence:
            print(f"[{idx:>3}/{total}] [SKIP] #{vimeo_id} ('{current_title}'): Confidence {conf:.2f} < {min_confidence:.2f}.")
            skipped += 1
            continue

        # Skip if already renamed
        if current_title == proposed_title:
            print(f"[{idx:>3}/{total}] [NOOP] #{vimeo_id} already has title '{current_title}'.")
            skipped += 1
            continue

        if dry_run:
            print(f"[{idx:>3}/{total}] [DRY-RUN] #{vimeo_id}: '{current_title}' -> '{proposed_title}'")
            updated += 1
            continue

        # Live PATCH Request
        url = f"{VIMEO_API_BASE}/videos/{vimeo_id}"
        payload = json.dumps({"name": proposed_title})
        max_retries = 5
        success = False

        for attempt in range(1, max_retries + 1):
            try:
                if HAS_REQUESTS:
                    resp = session.patch(url, data=payload, timeout=30)
                    status_code = resp.status_code
                    resp_headers = resp.headers
                    resp_text = resp.text
                else:
                    req = urllib.request.Request(url, data=payload.encode("utf-8"), headers=headers, method="PATCH")
                    try:
                        with urllib.request.urlopen(req, timeout=30) as r:
                            status_code = r.status
                            resp_headers = dict(r.info())
                            resp_text = r.read().decode("utf-8")
                    except urllib.error.HTTPError as he:
                        status_code = he.code
                        resp_headers = dict(he.headers)
                        resp_text = he.read().decode("utf-8")

                # Rate limiting check
                if status_code == 429:
                    retry_after = resp_headers.get("Retry-After") or resp_headers.get("retry-after")
                    wait_sec = float(retry_after) + 1.0 if retry_after else float(2 ** attempt * 5)
                    print(f"      [WARN] Rate limited (429). Waiting {wait_sec:.1f}s (Attempt {attempt}/{max_retries})...")
                    time.sleep(wait_sec)
                    continue

                if status_code == 401:
                    print(f"[ERROR] Vimeo 401 Unauthorized: Invalid access token.", file=sys.stderr)
                    sys.exit(1)

                if status_code == 200:
                    print(f"[{idx:>3}/{total}] [OK] #{vimeo_id}: '{current_title}' -> '{proposed_title}'")
                    updated += 1
                    success = True
                    break

                if status_code in (500, 502, 503, 504):
                    wait_sec = float(2 ** attempt * 2)
                    print(f"      [WARN] Vimeo server error ({status_code}). Retrying in {wait_sec:.1f}s...")
                    time.sleep(wait_sec)
                    continue

                print(f"[{idx:>3}/{total}] [FAIL] #{vimeo_id} ({status_code}): {resp_text[:120]}")
                failed += 1
                break

            except Exception as net_err:
                wait_sec = float(2 ** attempt * 2)
                print(f"      [WARN] Network error on #{vimeo_id}: {net_err}. Retrying in {wait_sec:.1f}s...")
                time.sleep(wait_sec)

        if not success and status_code == 429:
            print(f"[{idx:>3}/{total}] [FAIL] #{vimeo_id}: Exceeded retries due to rate limit.")
            failed += 1

        # Small courtesy delay between API calls
        time.sleep(0.15)

    print("\n" + "=" * 64)
    print("VIMEO BATCH RENAME RESULTS")
    print("=" * 64)
    print(f"Total videos processed:  {total:>4}")
    print(f"Successfully updated:    {updated:>4}")
    print(f"Skipped / unmapped:      {skipped:>4}")
    print(f"Failed updates:          {failed:>4}")
    print("=" * 64)


def main():
    parser = argparse.ArgumentParser(
        description="Vimeo Catalog Reconciler and Batch Renaming Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--plan",
        action="store_true",
        help="Generate reconciliation plan CSV without modifying Vimeo.",
    )
    mode_group.add_argument(
        "--apply",
        action="store_true",
        help="Apply batch renaming to Vimeo via API based on plan CSV.",
    )

    parser.add_argument(
        "--audit-csv",
        type=str,
        default=DEFAULT_AUDIT_CSV,
        help=f"Input Vimeo catalog audit CSV (default: '{DEFAULT_AUDIT_CSV}').",
    )
    parser.add_argument(
        "--legacy-csv",
        type=str,
        default=DEFAULT_LEGACY_CSV,
        help=f"Input legacy bucket export CSV (default: '{DEFAULT_LEGACY_CSV}').",
    )
    parser.add_argument(
        "--plan-csv",
        type=str,
        default=DEFAULT_PLAN_CSV,
        help=f"Path to output/input plan CSV (default: '{DEFAULT_PLAN_CSV}').",
    )
    parser.add_argument(
        "--token",
        type=str,
        default=None,
        help="Vimeo Access Token (defaults to VIMEO_ACCESS_TOKEN from env or .env).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate --apply without making actual Vimeo API calls.",
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.7,
        help="Minimum confidence score required to apply rename (default: 0.70).",
    )

    args = parser.parse_args()

    # Default to --plan if neither is explicitly passed
    if not args.plan and not args.apply:
        print("[INFO] No mode specified (--plan or --apply). Defaulting to --plan (dry-run reconciliation).\n")
        args.plan = True

    if args.plan:
        generate_plan(args.audit_csv, args.legacy_csv, args.plan_csv)
    elif args.apply:
        token = resolve_vimeo_token(args.token)
        apply_renames(args.plan_csv, token, dry_run=args.dry_run, min_confidence=args.min_confidence)


if __name__ == "__main__":
    main()
