#!/usr/bin/env python3
"""
Build the clean JSON data file that the static site consumes.

Reads:
  - data/mega_list.json (raw non-compliance data)
  - data/judges_crossref.json (normalized judges + appointer data)
  - data/litigation_tracker.db (structural litigation cases)

Writes:
  - site/data.json (everything the frontend needs)
"""

import json
import re
import sqlite3
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
SITE_DIR = BASE_DIR / "site"

SITE_DIR.mkdir(parents=True, exist_ok=True)

# ── Violation type normalization ──
# Map raw strings to canonical categories
VIOLATION_TYPE_MAP = {
    "failure to file": "Failure to File",
    "failure to file update/report; failure to respond/answer": "Failure to File",
    "failure to file update/report": "Failure to File",
    "failure to respond/answer": "Failure to File",

    "failure to timely release": "Failure to Timely Release",
    "failure to release": "Failure to Timely Release",

    "failure to return property": "Failure to Return Property",
    "failure to return propertyi": "Failure to Return Property",

    "transfer despite order": "Transfer Despite Order",
    "transfer despite court order": "Transfer Despite Order",
    "unauthorized transfer": "Transfer Despite Order",

    "failure to return detainee": "Failure to Return Detainee",

    "imposed conditions on release in violation of order": "Imposed Conditions in Violation of Order",
    "imposed conditions on release in violation of court order": "Imposed Conditions in Violation of Order",
    "imposed conditions in violation of order": "Imposed Conditions in Violation of Order",
    "imposed conditions in violation of court order": "Imposed Conditions in Violation of Order",
    "imposed conditions in violation of terms of court order": "Imposed Conditions in Violation of Order",
    "imposed conditions on release in violation of terms of court order": "Imposed Conditions in Violation of Order",

    "failure to provide bond hearing": "Failure to Provide Bond Hearing",
    "failure to hold bond hearing": "Failure to Provide Bond Hearing",

    "failure to produce evidence": "Failure to Produce Evidence",
    "failure to provide evidence": "Failure to Produce Evidence",

    "failure to coordinate with counsel": "Failure to Coordinate with Counsel",

    "removal despite order": "Removal/Deportation Despite Order",
    "removal despite court order": "Removal/Deportation Despite Order",
    "removal/deportation despite order": "Removal/Deportation Despite Order",
    "removal/deportation despite court order": "Removal/Deportation Despite Order",

    "misrepresentation to the court": "Misrepresentation to the Court",

    "failure to provide detainee medication": "Failure to Provide Detainee Medication",

    "failure to produce detainee": "Failure to Produce Detainee",

    "misc": "Miscellaneous",
    "misc ": "Miscellaneous",
    "miscellaneous": "Miscellaneous",
}

# Severity ordering (most severe first)
VIOLATION_SEVERITY = [
    "Removal/Deportation Despite Order",
    "Transfer Despite Order",
    "Failure to Return Detainee",
    "Failure to Timely Release",
    "Failure to Provide Detainee Medication",
    "Imposed Conditions in Violation of Order",
    "Failure to Return Property",
    "Failure to Provide Bond Hearing",
    "Failure to Produce Detainee",
    "Failure to Produce Evidence",
    "Misrepresentation to the Court",
    "Failure to Coordinate with Counsel",
    "Failure to File",
    "Miscellaneous",
]


def normalize_violation_types(raw: str) -> list[str]:
    """Parse and normalize semicolon-delimited violation types."""
    if not raw or not raw.strip():
        return []

    types = []
    for part in re.split(r'[;]', raw):
        part = part.strip()
        if not part:
            continue
        normalized = VIOLATION_TYPE_MAP.get(part.lower().strip(), None)
        if normalized:
            if normalized not in types:
                types.append(normalized)
        else:
            # Try to match substring
            matched = False
            for key, val in VIOLATION_TYPE_MAP.items():
                if key in part.lower():
                    if val not in types:
                        types.append(val)
                    matched = True
                    break
            if not matched:
                # Keep as-is but title-case
                cleaned = part.strip()
                if cleaned and cleaned not in types:
                    types.append(cleaned)

    return types


# ── Judge name normalization (same as normalize_judges.py) ──

MERGE_MAP = {
    "Patrick J. Schlitz": "Patrick J. Schiltz",
    "Laura M. Provenzino": "Laura M. Provinzino",
    "Laura M Provinzino": "Laura M. Provinzino",
    "Michael J. David": "Michael J. Davis",
    "Zahid Nisar Quraishi": "Zahid N. Quraishi",
    "Katharine Sweeney Hayden": "Katharine S. Hayden",
    "Renee Marie Bumb": "Renee M. Bumb",
    "James Boasberg": "James E. Boasberg",
    "Araceli Martínez-Olguín": "Araceli Martinez-Olguin",
    "Diana Saldaña": "Diana Saldana",
}


def strip_prefix(name: str) -> str:
    name = re.sub(r'\s+of the\s+.*$', '', name)
    prefixes = [
        r'U\.S\.\s+District\s+Chief\s+Judge\s+',
        r'U\.S\.\s+Senior\s+District\s+Judge\s+',
        r'U\.S\.\s+Visiting\s+District\s+Judge\s+',
        r'U\.S\.\s+Magistrate\s+Judge\s+',
        r'U\.S\.\s+District\s+Judge\.?\s+',
        r'U\.S\.\s+DIstrict\s+Judge\s+',
        r'U\.S\.\s+Distrct\s+Judge\s+',
        r'U\.S\.\s+District\s+',
        r'U\.S\s+District\s+Judge\s+',
        r'Chief\s+U\.S\.\s+District\s+Judge\s+',
        r'Senior\s+U\.S\.\s+District\s+Judge\s+',
    ]
    for prefix in prefixes:
        name = re.sub('^' + prefix, '', name, flags=re.IGNORECASE)
    return name.strip()


def normalize_unicode(name: str) -> str:
    nfkd = unicodedata.normalize('NFKD', name)
    return ''.join(c for c in nfkd if not unicodedata.category(c).startswith('M'))


def normalize_judge_name(raw_name: str) -> str:
    name = raw_name.strip()
    name = strip_prefix(name)
    name = normalize_unicode(name)
    if name in MERGE_MAP:
        name = MERGE_MAP[name]
    return name


def parse_dates(date_str: str) -> list[str]:
    """Parse date field which may have multiple dates like '1) 1/23/2025 ; 2) 1/28/2025'."""
    if not date_str:
        return []
    dates = []
    for part in re.split(r'[;]', date_str):
        # Strip numbering like "1) " or "2) "
        part = re.sub(r'^\d+\)\s*', '', part.strip())
        part = part.strip()
        if part:
            dates.append(part)
    return dates


def main():
    # ── Load raw data ──
    with open(DATA_DIR / "mega_list.json") as f:
        mega = json.load(f)
    rows = mega["values"]

    with open(DATA_DIR / "judges_crossref.json") as f:
        crossref = json.load(f)

    conn = sqlite3.connect(DATA_DIR / "litigation_tracker.db")
    conn.row_factory = sqlite3.Row

    # ── Build cases ──
    cases = []
    violation_type_counts = Counter()
    jurisdiction_counts = Counter()
    all_violation_combos = Counter()

    for i, r in enumerate(rows[1:], start=1):
        if len(r) < 10:
            continue

        case_name = r[0] if r[0] else ""
        case_no = r[1] if r[1] else ""
        jurisdiction = r[2] if r[2] else ""
        date_raw = r[3] if r[3] else ""
        description = r[4] if r[4] else ""
        judge_raw = r[5] if len(r) > 5 and r[5] else ""
        link_filing = r[6] if len(r) > 6 else ""
        docket_entry = r[7] if len(r) > 7 else ""
        link_docket = r[8] if len(r) > 8 else ""
        violation_raw = r[9] if len(r) > 9 else ""
        egregious = r[10] if len(r) > 10 else ""

        judge_normalized = normalize_judge_name(judge_raw) if judge_raw else ""
        violation_types = normalize_violation_types(violation_raw)
        dates = parse_dates(date_raw)

        # Get appointer from crossref
        appointed_by = None
        judge_info = crossref["judges"].get(judge_normalized)
        if judge_info:
            appointed_by = judge_info.get("appointed_by")

        for vt in violation_types:
            violation_type_counts[vt] += 1
        jurisdiction_counts[jurisdiction] += 1

        # Track co-occurrences
        if len(violation_types) > 1:
            combo = tuple(sorted(violation_types))
            all_violation_combos[combo] += 1

        case = {
            "id": i,
            "case_name": case_name,
            "case_no": case_no,
            "jurisdiction": jurisdiction,
            "dates": dates,
            "date_raw": date_raw,
            "description": description,
            "judge": judge_normalized,
            "judge_raw": judge_raw,
            "appointed_by": appointed_by,
            "violation_types": violation_types,
            "egregious": egregious.strip().lower() in ("yes", "y", "true", "1", "x"),
            "link_docket": link_docket,
            "link_filing": link_filing,
            "num_violations": len(violation_types),
        }
        cases.append(case)

    # ── Build judge profiles ──
    judges = {}
    for name, info in crossref["judges"].items():
        nc_case_ids = [c["id"] for c in cases if c["judge"] == name]

        # Violation type breakdown for this judge
        judge_violations = Counter()
        for c in cases:
            if c["judge"] == name:
                for vt in c["violation_types"]:
                    judge_violations[vt] += 1

        # Get litigation tracker cases if overlap
        lit_cases = []
        if info.get("in_litigation_tracker") and info.get("lit_cases"):
            for lc in info["lit_cases"]:
                lit_cases.append({
                    "case_name": lc["case_name"],
                    "docket_number": lc.get("docket_number"),
                    "executive_action": lc.get("executive_action"),
                    "status": lc.get("status"),
                })

        judges[name] = {
            "name": name,
            "appointed_by": info.get("appointed_by"),
            "nc_case_count": info["nc_case_count"],
            "nc_case_ids": nc_case_ids,
            "in_litigation_tracker": info.get("in_litigation_tracker", False),
            "lit_case_count": info.get("lit_case_count", 0),
            "lit_cases": lit_cases,
            "violation_breakdown": dict(judge_violations.most_common()),
        }

    # ── Build overlap judges (sorted by total involvement) ──
    overlap_judges = []
    for name, j in judges.items():
        if j["in_litigation_tracker"]:
            overlap_judges.append({
                "name": name,
                "appointed_by": j["appointed_by"],
                "nc_cases": j["nc_case_count"],
                "lit_cases": j["lit_case_count"],
                "total": j["nc_case_count"] + j["lit_case_count"],
                "lit_case_details": j["lit_cases"],
                "violation_breakdown": j["violation_breakdown"],
            })
    overlap_judges.sort(key=lambda x: -x["total"])

    # ── Build violation co-occurrence matrix ──
    cooccurrence = defaultdict(lambda: defaultdict(int))
    for c in cases:
        vts = c["violation_types"]
        for i, a in enumerate(vts):
            for b in vts[i+1:]:
                cooccurrence[a][b] += 1
                cooccurrence[b][a] += 1

    cooccurrence_list = []
    seen_pairs = set()
    for a in cooccurrence:
        for b in cooccurrence[a]:
            pair = tuple(sorted([a, b]))
            if pair not in seen_pairs:
                seen_pairs.add(pair)
                cooccurrence_list.append({
                    "source": pair[0],
                    "target": pair[1],
                    "count": cooccurrence[a][b],
                })
    cooccurrence_list.sort(key=lambda x: -x["count"])

    # ── Build timeline data ──
    # Parse first date of each case into a sortable format
    from datetime import datetime
    timeline = defaultdict(lambda: {"total": 0, "by_type": defaultdict(int), "by_jurisdiction": defaultdict(int)})

    for c in cases:
        if not c["dates"]:
            continue
        first_date = c["dates"][0]
        # Try to parse date
        for fmt in ("%m/%d/%Y", "%m/%d/%y", "%m/%d/%Y ", "%m/%d/%y "):
            try:
                dt = datetime.strptime(first_date.strip(), fmt)
                # Weekly bucket
                week_key = dt.strftime("%Y-W%U")
                month_key = dt.strftime("%Y-%m")
                timeline[month_key]["total"] += 1
                for vt in c["violation_types"]:
                    timeline[month_key]["by_type"][vt] += 1
                timeline[month_key]["by_jurisdiction"][c["jurisdiction"]] += 1
                break
            except ValueError:
                continue

    timeline_sorted = []
    for month in sorted(timeline.keys()):
        entry = timeline[month]
        timeline_sorted.append({
            "month": month,
            "total": entry["total"],
            "by_type": dict(entry["by_type"]),
            "by_jurisdiction": dict(entry["by_jurisdiction"]),
        })

    # ── Summary stats ──
    appointer_dist = Counter()
    appointer_case_dist = Counter()
    for c in cases:
        if c["appointed_by"]:
            appointer_dist[c["appointed_by"]] += 1

    for name, j in judges.items():
        if j["appointed_by"]:
            appointer_case_dist[j["appointed_by"]] += j["nc_case_count"]

    summary = {
        "total_cases": len(cases),
        "total_judges": len(judges),
        "judges_with_appointer": sum(1 for j in judges.values() if j.get("appointed_by")),
        "overlap_judge_count": len(overlap_judges),
        "total_jurisdictions": len(jurisdiction_counts),
        "cases_before_overlap_judges": sum(j["nc_cases"] for j in overlap_judges),
        "egregious_count": sum(1 for c in cases if c["egregious"]),
        "multi_violation_cases": sum(1 for c in cases if c["num_violations"] > 1),
        "violation_type_counts": dict(violation_type_counts.most_common()),
        "jurisdiction_counts": dict(jurisdiction_counts.most_common()),
        "appointer_distribution": dict(appointer_dist.most_common()),
        "violation_severity_order": VIOLATION_SEVERITY,
    }

    # ── Assemble output ──
    output = {
        "summary": summary,
        "cases": cases,
        "judges": judges,
        "overlap_judges": overlap_judges,
        "cooccurrence": cooccurrence_list,
        "timeline": timeline_sorted,
    }

    out_path = SITE_DIR / "data.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Wrote {out_path} ({out_path.stat().st_size / 1024:.0f} KB)")
    print(f"  {len(cases)} cases")
    print(f"  {len(judges)} judges ({len(overlap_judges)} overlap)")
    print(f"  {len(cooccurrence_list)} violation co-occurrence pairs")
    print(f"  {len(timeline_sorted)} months in timeline")
    print(f"\nViolation types:")
    for vt, count in violation_type_counts.most_common():
        print(f"  {count:4d}  {vt}")
    print(f"\nTop co-occurrences:")
    for co in cooccurrence_list[:10]:
        print(f"  {co['count']:3d}  {co['source']} + {co['target']}")


if __name__ == "__main__":
    main()
