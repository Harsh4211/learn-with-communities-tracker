"""
CSV Handler for customizable student rosters and report exporting.
"""
import csv
import io
from typing import List, Dict, Any, Union
from datetime import datetime

URL_COLUMN_ALIASES = [
    "google skills profile url",
    "google skills public profile url",
    "google skills public profile urls",
    "profile url",
    "profile_url",
    "public_profile_url",
    "url",
    "profile",
    "link"
]

INFO_COLUMN_ALIASES = [
    "[info]",
    "info",
    "notes",
    "note",
    "remarks",
    "description"
]

NAME_COLUMN_ALIASES = [
    "student name",
    "candidate name",
    "name",
    "student",
    "full name"
]


def parse_csv_data(content_or_path: Union[str, bytes]) -> List[Dict[str, str]]:
    """
    Parses CSV content or file path into a standardized list of candidate targets.
    Returns: [{'url': '...', 'info': '...', 'name': '...'}]
    """
    if isinstance(content_or_path, bytes):
        text = content_or_path.decode('utf-8-sig', errors='replace')
    elif isinstance(content_or_path, str) and ("\n" not in content_or_path and len(content_or_path) < 300):
        # Likely a file path
        with open(content_or_path, 'r', encoding='utf-8-sig') as f:
            text = f.read()
    else:
        text = content_or_path

    reader = csv.reader(io.StringIO(text.strip()))
    rows = list(reader)
    if not rows:
        return []

    header = [c.strip().lower() for c in rows[0]]
    
    url_col_idx = -1
    info_col_idx = -1
    name_col_idx = -1

    for idx, col in enumerate(header):
        if col in URL_COLUMN_ALIASES or "skill" in col and "url" in col:
            url_col_idx = idx
        elif col in INFO_COLUMN_ALIASES:
            info_col_idx = idx
        elif col in NAME_COLUMN_ALIASES:
            name_col_idx = idx

    # If header didn't match known aliases, check if row 0 itself is a URL (headerless CSV)
    has_header = True
    if url_col_idx == -1:
        if "http" in rows[0][0]:
            has_header = False
            url_col_idx = 0
            if len(rows[0]) > 1:
                info_col_idx = 1
        else:
            # Default to first column if no alias matches
            url_col_idx = 0
            if len(rows[0]) > 1:
                info_col_idx = 1

    records = []
    data_rows = rows[1:] if has_header else rows

    for row_idx, r in enumerate(data_rows, start=1):
        if not r or len(r) <= url_col_idx:
            continue
        url = r[url_col_idx].strip()
        if not url:
            continue

        info = r[info_col_idx].strip() if info_col_idx != -1 and len(r) > info_col_idx else ""
        name = r[name_col_idx].strip() if name_col_idx != -1 and len(r) > name_col_idx else ""

        records.append({
            "url": url,
            "info": info,
            "name": name,
            "row_number": row_idx
        })

    return records


def export_results_csv(results: List[Dict[str, Any]], filepath: str = None) -> str:
    """Exports structured scan results to a clean CSV format."""
    output = io.StringIO()
    writer = csv.writer(output)

    # Headers
    writer.writerow([
        "Candidate Name",
        "Status",
        "Campaign Badges Completed (Out of 10)",
        "Completion Percentage",
        "Total Profile Badges",
        "Google Skills Profile URL",
        "Original Notes / INFO",
        "Completed Campaign Badges",
        "Missing Campaign Badges",
        "Report Generated At"
    ])

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for item in results:
        earned_names = "; ".join([b["title"] for b in item.get("earned_campaign_badges", [])])
        missing_names = "; ".join([b["title"] for b in item.get("missing_campaign_badges", [])])
        
        writer.writerow([
            item.get("name", "Unknown"),
            item.get("status_label", item.get("status", "")),
            f"{item.get('campaign_completed', 0)}/10",
            f"{item.get('completion_percentage', 0.0)}%",
            item.get("total_badges", 0),
            item.get("url", ""),
            item.get("original_info", ""),
            earned_names,
            missing_names,
            now_str
        ])

    csv_text = output.getvalue()
    if filepath:
        with open(filepath, "w", encoding="utf-8-sig", newline="") as f:
            f.write(csv_text)

    return csv_text
