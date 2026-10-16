#!/usr/bin/env python3
"""
Simple Solutions Ecosystem - Vimeo Catalog Audit Extractor
Path: scripts/audit_vimeo_catalog.py

Audits the Vimeo video library by fetching:
1. All folders/projects via GET https://api.vimeo.com/me/projects
2. Paginated videos per folder via GET https://api.vimeo.com/me/projects/{project_id}/videos
3. Root / unassigned videos via GET https://api.vimeo.com/me/videos

Outputs an audit catalog CSV to data/migration/vimeo_catalog_audit.csv with:
- vimeo_id
- title
- folder_name
- duration_seconds
- privacy_view
- privacy_embed
- link
- thumbnail_default_url
"""

import os
import sys
import csv
import time
import json
import re
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

DEFAULT_OUTPUT_CSV = "data/migration/vimeo_catalog_audit.csv"
VIMEO_API_BASE = "https://api.vimeo.com"


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
    print("Please set VIMEO_ACCESS_TOKEN in .env or run with: python3 scripts/audit_vimeo_catalog.py --token <YOUR_TOKEN>", file=sys.stderr)
    sys.exit(1)


class VimeoClient:
    """Robust Vimeo API HTTP client with rate-limiting & pagination support."""

    def __init__(self, access_token: str):
        self.access_token = access_token
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.vimeo.*+json;version=3.4",
            "User-Agent": "SimpleSolutions-VimeoAuditor/1.0",
        }
        if HAS_REQUESTS:
            self.session = requests.Session()
            self.session.headers.update(self.headers)

    def request(self, endpoint_or_url: str, params: Optional[Dict[str, Any]] = None, max_retries: int = 5) -> Dict[str, Any]:
        """Make an authenticated GET request with rate limit handling and retries."""
        if endpoint_or_url.startswith("http://") or endpoint_or_url.startswith("https://"):
            url = endpoint_or_url
        else:
            url = f"{VIMEO_API_BASE.rstrip('/')}/{endpoint_or_url.lstrip('/')}"

        for attempt in range(1, max_retries + 1):
            try:
                if HAS_REQUESTS:
                    resp = self.session.get(url, params=params, timeout=30)
                    status_code = resp.status_code
                    headers = resp.headers
                    text = resp.text
                else:
                    req_url = url
                    if params:
                        encoded = urllib.parse.urlencode(params)
                        req_url = f"{url}?{encoded}" if "?" not in url else f"{url}&{encoded}"
                    req = urllib.request.Request(req_url, headers=self.headers)
                    try:
                        with urllib.request.urlopen(req, timeout=30) as r:
                            status_code = r.status
                            headers = dict(r.info())
                            text = r.read().decode("utf-8")
                    except urllib.error.HTTPError as he:
                        status_code = he.code
                        headers = dict(he.headers)
                        text = he.read().decode("utf-8")

                # Check rate-limit remaining headers
                rate_limit_rem = headers.get("x-ratelimit-remaining") or headers.get("X-RateLimit-Remaining")
                rate_limit_reset = headers.get("x-ratelimit-reset") or headers.get("X-RateLimit-Reset")

                if rate_limit_rem is not None:
                    try:
                        rem_val = int(rate_limit_rem)
                        if rem_val <= 3:
                            print(f"[WARN] Vimeo API rate limit low: {rem_val} calls remaining. Reset at {rate_limit_reset}.", file=sys.stderr)
                    except ValueError:
                        pass

                # Success
                if status_code == 200:
                    return json.loads(text)

                # Rate limited
                if status_code == 429:
                    retry_after = headers.get("Retry-After") or headers.get("retry-after")
                    wait_seconds = 10.0
                    if retry_after:
                        try:
                            wait_seconds = float(retry_after) + 1.0
                        except ValueError:
                            pass
                    elif rate_limit_reset:
                        # Reset is an ISO timestamp or epoch
                        try:
                            if rate_limit_reset.isdigit():
                                diff = int(rate_limit_reset) - time.time()
                                wait_seconds = max(1.0, diff + 1.0)
                            else:
                                reset_dt = datetime.fromisoformat(rate_limit_reset.replace("Z", "+00:00"))
                                wait_seconds = max(1.0, (reset_dt.timestamp() - time.time()) + 1.0)
                        except Exception:
                            wait_seconds = float(2 ** attempt * 5)
                    else:
                        wait_seconds = float(2 ** attempt * 5)

                    print(f"[WARN] Rate limit hit (429). Backing off for {wait_seconds:.1f}s (Attempt {attempt}/{max_retries})...", file=sys.stderr)
                    time.sleep(wait_seconds)
                    continue

                if status_code == 401:
                    print(f"[ERROR] Vimeo API 401 Unauthorized: Access token is invalid or lacks required scopes.", file=sys.stderr)
                    sys.exit(1)

                if status_code in (500, 502, 503, 504):
                    wait_seconds = float(2 ** attempt * 2)
                    print(f"[WARN] Vimeo API server error ({status_code}). Retrying in {wait_seconds:.1f}s...", file=sys.stderr)
                    time.sleep(wait_seconds)
                    continue

                # Other HTTP errors
                raise RuntimeError(f"Vimeo API request failed [{status_code}]: {text}")

            except (urllib.error.URLError, ConnectionError, TimeoutError) as net_err:
                wait_seconds = float(2 ** attempt * 2)
                print(f"[WARN] Network error: {net_err}. Retrying in {wait_seconds:.1f}s (Attempt {attempt}/{max_retries})...", file=sys.stderr)
                time.sleep(wait_seconds)

        raise RuntimeError(f"Exceeded max retries ({max_retries}) for URL: {url}")

    def paginate(self, endpoint_or_url: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Paginate through all results for a given Vimeo endpoint."""
        results: List[Dict[str, Any]] = []
        current_params = dict(params or {})
        current_params.setdefault("per_page", 100)
        current_params.setdefault("page", 1)

        while True:
            data = self.request(endpoint_or_url, params=current_params)
            items = data.get("data", [])
            results.extend(items)

            paging = data.get("paging") or {}
            next_url = paging.get("next")
            total = data.get("total", len(results))

            # Stop condition: next is null or no items returned or reached total
            if not next_url or not items or len(results) >= total:
                break

            current_params["page"] += 1

        return results


def extract_vimeo_id(uri: Optional[str]) -> str:
    """Extract numeric ID suffix from URI (e.g., '/videos/1236558679' -> '1236558679')."""
    if not uri:
        return ""
    match = re.search(r"(\d+)$", uri.strip())
    return match.group(1) if match else uri.rstrip("/").split("/")[-1]


def extract_thumbnail_url(pictures: Optional[Dict[str, Any]]) -> str:
    """Extract the default or highest resolution thumbnail URL from pictures payload."""
    if not pictures:
        return ""
    base_link = pictures.get("base_link")
    if base_link:
        return base_link
    sizes = pictures.get("sizes") or []
    if sizes:
        # sizes are sorted ascending by size; pick the last / highest res
        return sizes[-1].get("link", "")
    return ""


def parse_video_record(video: Dict[str, Any], folder_name: str) -> Dict[str, Any]:
    """Format raw Vimeo video item into standardized catalog record."""
    uri = video.get("uri") or ""
    vimeo_id = extract_vimeo_id(uri)
    title = video.get("name") or ""
    duration = int(video.get("duration") or 0)
    privacy = video.get("privacy") or {}
    privacy_view = privacy.get("view") or ""
    privacy_embed = privacy.get("embed") or ""
    link = video.get("link") or f"https://vimeo.com/{vimeo_id}" if vimeo_id else ""
    pictures = video.get("pictures")
    thumbnail_default_url = extract_thumbnail_url(pictures)

    return {
        "vimeo_id": vimeo_id,
        "title": title,
        "folder_name": folder_name,
        "duration_seconds": duration,
        "privacy_view": privacy_view,
        "privacy_embed": privacy_embed,
        "link": link,
        "thumbnail_default_url": thumbnail_default_url,
    }


def audit_vimeo_catalog(token: str, output_csv_path: str) -> None:
    """Execute complete Vimeo audit extraction and generate CSV catalog."""
    print("=" * 64)
    print("Simple Solutions - Vimeo Catalog Audit Extractor")
    print("=" * 64)

    client = VimeoClient(token)

    # 1. Fetch all folders / projects
    print("[1/3] Fetching all folders/projects via GET /me/projects...")
    projects = client.paginate("/me/projects", params={"per_page": 100})
    print(f"      Found {len(projects)} total projects/folders.")

    folder_map: List[Tuple[str, str]] = []  # List of (project_id, folder_name)
    folder_video_counts: Dict[str, int] = {}

    for p in projects:
        p_uri = p.get("uri") or ""
        p_id = extract_vimeo_id(p_uri)
        p_name = p.get("name") or f"Project_{p_id}"
        folder_map.append((p_id, p_name))
        folder_video_counts[p_name] = 0

    catalog_records: List[Dict[str, Any]] = []
    seen_vimeo_ids: Set[str] = set()

    # 2. For each folder, paginate through videos
    print("\n[2/3] Extracting videos per folder via GET /me/projects/{project_id}/videos...")
    for p_id, p_name in folder_map:
        endpoint = f"/me/projects/{p_id}/videos"
        videos = client.paginate(endpoint, params={"per_page": 100})
        folder_video_counts[p_name] = len(videos)

        for v in videos:
            rec = parse_video_record(v, folder_name=p_name)
            v_id = rec["vimeo_id"]
            if v_id and v_id not in seen_vimeo_ids:
                seen_vimeo_ids.add(v_id)
                catalog_records.append(rec)
            elif not v_id:
                catalog_records.append(rec)

        print(f"      Folder: '{p_name}' (ID: {p_id}) -> {len(videos)} videos extracted.")

    # 3. Capture root / unassigned videos via GET /me/videos
    print("\n[3/3] Checking root/unassigned videos via GET /me/videos...")
    all_videos = client.paginate("/me/videos", params={"per_page": 100})
    print(f"      Retrieved {len(all_videos)} total account videos.")

    unassigned_count = 0
    newly_captured_from_root = 0

    for v in all_videos:
        v_uri = v.get("uri") or ""
        v_id = extract_vimeo_id(v_uri)
        parent_folder = v.get("parent_folder")

        if v_id not in seen_vimeo_ids:
            # Video was not found in any project query
            if parent_folder and parent_folder.get("name"):
                f_name = parent_folder["name"]
                if f_name not in folder_video_counts:
                    folder_video_counts[f_name] = 0
                folder_video_counts[f_name] += 1
            else:
                f_name = ""
                unassigned_count += 1

            rec = parse_video_record(v, folder_name=f_name)
            seen_vimeo_ids.add(v_id)
            catalog_records.append(rec)
            newly_captured_from_root += 1
        else:
            # Already seen, but if it had no parent folder, track unassigned
            if not parent_folder:
                unassigned_count += 1

    if newly_captured_from_root > 0:
        print(f"      Captured {newly_captured_from_root} additional videos from /me/videos.")
    else:
        print("      All account videos were already cataloged across folders.")

    # 4. Save to CSV
    out_path = Path(output_csv_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "vimeo_id",
        "title",
        "folder_name",
        "duration_seconds",
        "privacy_view",
        "privacy_embed",
        "link",
        "thumbnail_default_url",
    ]

    with open(out_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in catalog_records:
            writer.writerow(row)

    # 5. Print summary breakdown to console
    print("\n" + "=" * 64)
    print("VIMEO CATALOG AUDIT SUMMARY BREAKDOWN")
    print("=" * 64)
    print(f"Total videos audited & written: {len(catalog_records)}")
    print(f"Total unassigned (root) videos:  {unassigned_count}")
    print("\nBreakdown by Folder:")
    for f_name, count in sorted(folder_video_counts.items(), key=lambda x: x[0].lower()):
        print(f"  * {f_name:<30} : {count:>4} videos")
    if unassigned_count > 0:
        print(f"  * {'[Unassigned / Root]':<30} : {unassigned_count:>4} videos")
    print("=" * 64)
    print(f"Catalog successfully exported to: {out_path.resolve()}")
    print("=" * 64)


def main():
    parser = argparse.ArgumentParser(
        description="Audit and extract full Vimeo catalog into CSV.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--token",
        type=str,
        default=None,
        help="Vimeo Access Token (defaults to VIMEO_ACCESS_TOKEN from env or .env).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=DEFAULT_OUTPUT_CSV,
        help=f"Target output CSV file path (defaults to '{DEFAULT_OUTPUT_CSV}').",
    )

    args = parser.parse_args()
    token = resolve_vimeo_token(args.token)
    audit_vimeo_catalog(token, args.output)


if __name__ == "__main__":
    main()
