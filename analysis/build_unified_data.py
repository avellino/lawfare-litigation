#!/usr/bin/env python3
"""
Build unified data.json for the combined site.

Merges:
  - Litigation tracker data (from litigation_analysis.json + SQLite for parties/attorneys)
  - Non-compliance data (from mega_list.json + judges_crossref.json)

Outputs: site/data.json
"""

import json
import re
import sqlite3
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
SITE_DIR = BASE_DIR / "site"
SITE_DIR.mkdir(parents=True, exist_ok=True)

# ══════════════════════════════════════════════
# Shared helpers
# ══════════════════════════════════════════════

COURT_NAMES = {
    "dcd": "D.C. District Court", "cadc": "D.C. Circuit", "mad": "D. Mass.",
    "mdd": "D. Md.", "ca9": "Ninth Circuit", "nysd": "S.D.N.Y.",
    "cand": "N.D. Cal.", "ca1": "First Circuit", "rid": "D.R.I.",
    "ca4": "Fourth Circuit", "ilnd": "N.D. Ill.", "wawd": "W.D. Wash.",
    "mnd": "D. Minn.", "cit": "Court of Int'l Trade", "ca2": "Second Circuit",
    "cacd": "C.D. Cal.", "ord": "D. Or.", "njd": "D.N.J.", "cod": "D. Colo.",
    "gamd": "M.D. Ga.", "nhd": "D.N.H.", "vaed": "E.D. Va.", "nynd": "N.D.N.Y.",
    "paed": "E.D. Pa.", "nyed": "E.D.N.Y.", "txsd": "S.D. Tex.", "scd": "D.S.C.",
    "vtd": "D. Vt.", "txwd": "W.D. Tex.", "kyed": "E.D. Ky.", "nvd": "D. Nev.",
    "mtd": "D. Mont.", "med": "D. Me.", "wvsd": "S.D. W.Va.", "ca3": "Third Circuit",
    "azd": "D. Ariz.", "wiwd": "W.D. Wis.", "casd": "S.D. Cal.", "pawd": "W.D. Pa.",
    "txnd": "N.D. Tex.", "ca5": "Fifth Circuit", "ca10": "Tenth Circuit",
    "lawd": "W.D. La.", "hid": "D. Haw.", "miwd": "W.D. Mich.",
    "tnmd": "M.D. Tenn.", "cafc": "Federal Circuit", "pamd": "M.D. Pa.",
    "uscfc": "Court of Federal Claims", "akd": "D. Alaska", "ca7": "Seventh Circuit",
    "ca6": "Sixth Circuit", "flmd": "M.D. Fla.", "ilsd": "S.D. Ill.",
    "alsd": "S.D. Ala.", "ca8": "Eighth Circuit", "flsd": "S.D. Fla.",
    "gand": "N.D. Ga.", "ncwd": "W.D.N.C.",
}


def court_display_name(court_url):
    if not court_url or not isinstance(court_url, str):
        return court_url or ""
    m = re.search(r'/courts/([^/]+)/?$', court_url)
    if m:
        return COURT_NAMES.get(m.group(1), m.group(1).upper())
    return court_url


def categorize_status(status):
    if not status:
        return "Other"
    s = status.lower()
    if any(w in s for w in ["dismissed", "moot", "withdrawn", "terminated", "closed"]):
        return "Dismissed / Terminated"
    if any(w in s for w in ["appealed", "appeal filed", "cert", "writ"]):
        return "On Appeal"
    if any(w in s for w in ["upheld", "affirmed", "mandate returned", "remanded",
                             "overturned", "vacated", "rehearing", "en banc"]):
        return "Appellate Decision"
    if any(w in s for w in ["stay granted", "stay entered", "stayed", "stay and cert",
                             "partial stay", "abeyance", "postpone"]):
        return "Stayed"
    if any(w in s for w in ["stay denied", "stay denial", "stay dissolved"]):
        return "Stay Denied"
    if any(w in s for w in ["pi granted", "tro granted", "injunction granted",
                             "pi and class", "pi and partial", "class certified", "enjoined"]):
        return "Injunction / TRO Granted"
    if any(w in s for w in ["pi denied", "tro denied", "injunction denied"]):
        return "Injunction / TRO Denied"
    if "summary judg" in s:
        return "Summary Judgment"
    if any(w in s for w in ["suit filed", "complaint filed", "application filed",
                             "petition", "indictment"]):
        return "Pending / Filed"
    if any(w in s for w in ["consolidated", "venue"]):
        return "Procedural"
    return "Other"


# ══════════════════════════════════════════════
# Non-compliance normalization (same as before)
# ══════════════════════════════════════════════

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
    "misc": "Miscellaneous", "misc ": "Miscellaneous", "miscellaneous": "Miscellaneous",
}

VIOLATION_SEVERITY = [
    "Removal/Deportation Despite Order", "Transfer Despite Order",
    "Failure to Return Detainee", "Failure to Timely Release",
    "Failure to Provide Detainee Medication", "Imposed Conditions in Violation of Order",
    "Failure to Return Property", "Failure to Provide Bond Hearing",
    "Failure to Produce Detainee", "Failure to Produce Evidence",
    "Misrepresentation to the Court", "Failure to Coordinate with Counsel",
    "Failure to File", "Miscellaneous",
]

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


def strip_judge_prefix(name):
    name = re.sub(r'\s+of the\s+.*$', '', name)
    for prefix in [
        r'U\.S\.\s+District\s+Chief\s+Judge\s+', r'U\.S\.\s+Senior\s+District\s+Judge\s+',
        r'U\.S\.\s+Visiting\s+District\s+Judge\s+', r'U\.S\.\s+Magistrate\s+Judge\s+',
        r'U\.S\.\s+District\s+Judge\.?\s+', r'U\.S\.\s+DIstrict\s+Judge\s+',
        r'U\.S\.\s+Distrct\s+Judge\s+', r'U\.S\.\s+District\s+',
        r'U\.S\s+District\s+Judge\s+', r'Chief\s+U\.S\.\s+District\s+Judge\s+',
        r'Senior\s+U\.S\.\s+District\s+Judge\s+',
    ]:
        name = re.sub('^' + prefix, '', name, flags=re.IGNORECASE)
    return name.strip()


def normalize_judge_name(raw):
    name = strip_judge_prefix(raw.strip())
    nfkd = unicodedata.normalize('NFKD', name)
    name = ''.join(c for c in nfkd if not unicodedata.category(c).startswith('M'))
    return MERGE_MAP.get(name, name)


def normalize_violation_types(raw):
    if not raw or not raw.strip():
        return []
    types = []
    for part in re.split(r'[;]', raw):
        part = part.strip()
        if not part:
            continue
        normalized = VIOLATION_TYPE_MAP.get(part.lower().strip())
        if normalized:
            if normalized not in types:
                types.append(normalized)
        else:
            for key, val in VIOLATION_TYPE_MAP.items():
                if key in part.lower():
                    if val not in types:
                        types.append(val)
                    break
    return types


def parse_dates(date_str):
    if not date_str:
        return []
    dates = []
    for part in re.split(r'[;]', date_str):
        part = re.sub(r'^\d+\)\s*', '', part.strip()).strip()
        if part:
            dates.append(part)
    return dates


# ══════════════════════════════════════════════
# Build litigation tracker section
# ══════════════════════════════════════════════

def build_litigation_section():
    print("Building litigation tracker section...")

    with open(DATA_DIR / "litigation_analysis.json") as f:
        analysis = json.load(f)

    conn = sqlite3.connect(DATA_DIR / "litigation_tracker.db")

    # Cases
    cases = analysis.get("case_details", [])
    for c in cases:
        c["court_display"] = court_display_name(c.get("court", ""))
        c["status_category"] = categorize_status(c.get("status", ""))
        ea = c.get("base_executive_action") or c.get("executive_action") or ""
        c["executive_action_display"] = ea

    # Executive actions with status breakdown
    ea_status = defaultdict(lambda: defaultdict(int))
    for c in cases:
        ea = c["executive_action_display"]
        if ea:
            ea_status[ea][c["status_category"]] += 1

    ea_status_list = []
    for ea, statuses in ea_status.items():
        total = sum(statuses.values())
        ea_status_list.append({"executive_action": ea, "total": total, "statuses": dict(statuses)})
    ea_status_list.sort(key=lambda x: -x["total"])

    # Top attorneys with parties info
    attorney_rows = conn.execute("""
        SELECT a.name, a.role, a.organization, a.case_id
        FROM attorneys a
    """).fetchall()

    # Build attorney aggregations
    atty_by_role = defaultdict(lambda: defaultdict(set))
    for name, role, org, case_id in attorney_rows:
        atty_by_role[role][name].add(case_id)

    top_plaintiff_attorneys = sorted(
        [{"name": n, "case_count": len(cids)} for n, cids in atty_by_role.get("plaintiff_attorney", {}).items()],
        key=lambda x: -x["case_count"]
    )[:25]

    top_defendant_attorneys = sorted(
        [{"name": n, "case_count": len(cids)} for n, cids in atty_by_role.get("defendant_attorney", {}).items()],
        key=lambda x: -x["case_count"]
    )[:25]

    # Parties for case detail lookups
    party_rows = conn.execute("SELECT case_id, name, party_type FROM parties").fetchall()
    parties_by_case = defaultdict(list)
    for case_id, name, ptype in party_rows:
        parties_by_case[case_id].append({"name": name, "type": ptype})

    attorneys_by_case = defaultdict(list)
    for name, role, org, case_id in attorney_rows:
        attorneys_by_case[case_id].append({"name": name, "role": role, "organization": org or ""})

    # Attach parties/attorneys to case details
    for c in cases:
        cid = c.get("id")
        c["parties"] = parties_by_case.get(cid, [])
        c["attorneys"] = attorneys_by_case.get(cid, [])

    conn.close()

    overview = analysis.get("overview", {})

    return {
        "overview": overview,
        "cases": cases,
        "executive_actions": analysis.get("executive_actions", []),
        "ea_status_breakdown": ea_status_list[:30],
        "court_counts": analysis.get("court_counts", []),
        "judge_stats": analysis.get("judge_stats", []),
        "appointer_stats": analysis.get("appointer_stats", {}),
        "top_attorneys": {
            "plaintiff": top_plaintiff_attorneys,
            "defendant": top_defendant_attorneys,
        },
        "top_organizations": analysis.get("top_organizations", []),
        "timeline": analysis.get("timeline", []),
    }


# ══════════════════════════════════════════════
# Build non-compliance section
# ══════════════════════════════════════════════

def build_noncompliance_section():
    print("Building non-compliance section...")

    with open(DATA_DIR / "mega_list.json") as f:
        mega = json.load(f)
    rows = mega["values"]

    with open(DATA_DIR / "judges_crossref.json") as f:
        crossref = json.load(f)

    cases = []
    violation_type_counts = Counter()
    jurisdiction_counts = Counter()

    for i, r in enumerate(rows[1:], start=1):
        if len(r) < 10:
            continue

        judge_raw = r[5].strip() if len(r) > 5 and r[5] else ""
        judge_normalized = normalize_judge_name(judge_raw) if judge_raw else ""
        violation_types = normalize_violation_types(r[9] if len(r) > 9 else "")
        dates = parse_dates(r[3] if r[3] else "")

        appointed_by = None
        judge_info = crossref["judges"].get(judge_normalized)
        if judge_info:
            appointed_by = judge_info.get("appointed_by")

        for vt in violation_types:
            violation_type_counts[vt] += 1
        jurisdiction_counts[r[2] if r[2] else ""] += 1

        cases.append({
            "id": i,
            "case_name": r[0] if r[0] else "",
            "case_no": r[1] if r[1] else "",
            "jurisdiction": r[2] if r[2] else "",
            "dates": dates,
            "description": r[4] if r[4] else "",
            "judge": judge_normalized,
            "appointed_by": appointed_by,
            "violation_types": violation_types,
            "egregious": (r[10].strip().lower() in ("yes", "y", "true", "1", "x")) if len(r) > 10 and r[10] else False,
            "link_docket": r[8] if len(r) > 8 else "",
            "link_filing": r[6] if len(r) > 6 else "",
        })

    # Judge profiles
    judges = {}
    for name, info in crossref["judges"].items():
        nc_case_ids = [c["id"] for c in cases if c["judge"] == name]
        judge_violations = Counter()
        for c in cases:
            if c["judge"] == name:
                for vt in c["violation_types"]:
                    judge_violations[vt] += 1

        lit_cases = info.get("lit_cases", []) if info.get("in_litigation_tracker") else []
        judges[name] = {
            "name": name,
            "appointed_by": info.get("appointed_by"),
            "nc_case_count": info["nc_case_count"],
            "in_litigation_tracker": info.get("in_litigation_tracker", False),
            "lit_case_count": info.get("lit_case_count", 0),
            "lit_cases": lit_cases,
            "violation_breakdown": dict(judge_violations.most_common()),
        }

    # Overlap judges
    overlap_judges = sorted(
        [j for j in judges.values() if j["in_litigation_tracker"]],
        key=lambda x: -(x["nc_case_count"] + x["lit_case_count"])
    )

    # Co-occurrence
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
                cooccurrence_list.append({"source": pair[0], "target": pair[1], "count": cooccurrence[a][b]})
    cooccurrence_list.sort(key=lambda x: -x["count"])

    # Timeline
    timeline = defaultdict(lambda: {"total": 0, "by_type": defaultdict(int)})
    for c in cases:
        if not c["dates"]:
            continue
        for fmt in ("%m/%d/%Y", "%m/%d/%y"):
            try:
                dt = datetime.strptime(c["dates"][0].strip(), fmt)
                month_key = dt.strftime("%Y-%m")
                timeline[month_key]["total"] += 1
                for vt in c["violation_types"]:
                    timeline[month_key]["by_type"][vt] += 1
                break
            except ValueError:
                continue

    timeline_sorted = [{"month": m, "total": t["total"], "by_type": dict(t["by_type"])}
                       for m, t in sorted(timeline.items())]

    # Appointer distribution
    appointer_dist = Counter()
    for c in cases:
        if c["appointed_by"]:
            appointer_dist[c["appointed_by"]] += 1

    return {
        "summary": {
            "total_cases": len(cases),
            "total_judges": len(judges),
            "overlap_judge_count": len(overlap_judges),
            "total_jurisdictions": len(jurisdiction_counts),
            "multi_violation_cases": sum(1 for c in cases if len(c["violation_types"]) > 1),
            "egregious_count": sum(1 for c in cases if c["egregious"]),
            "violation_type_counts": dict(violation_type_counts.most_common()),
            "jurisdiction_counts": dict(jurisdiction_counts.most_common()),
            "appointer_distribution": dict(appointer_dist.most_common()),
            "violation_severity_order": VIOLATION_SEVERITY,
        },
        "cases": cases,
        "judges": judges,
        "overlap_judges": [{"name": j["name"], "appointed_by": j["appointed_by"],
                            "nc_cases": j["nc_case_count"], "lit_cases": j["lit_case_count"],
                            "total": j["nc_case_count"] + j["lit_case_count"],
                            "lit_case_details": j["lit_cases"],
                            "violation_breakdown": j["violation_breakdown"]}
                           for j in overlap_judges],
        "cooccurrence": cooccurrence_list,
        "timeline": timeline_sorted,
    }


# ══════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════

def main():
    lit = build_litigation_section()
    nc = build_noncompliance_section()

    output = {
        "litigation": lit,
        "noncompliance": nc,
    }

    out_path = SITE_DIR / "data.json"
    # Replace NaN/Infinity with None before serializing (pandas leaves NaN in dicts)
    import math
    def sanitize(obj):
        if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
            return None
        if isinstance(obj, dict):
            return {k: sanitize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [sanitize(v) for v in obj]
        return obj
    output = sanitize(output)
    with open(out_path, "w") as f:
        json.dump(output, f)  # no indent to reduce file size

    size_kb = out_path.stat().st_size / 1024
    print(f"\nWrote {out_path} ({size_kb:.0f} KB)")
    print(f"  Litigation: {len(lit['cases'])} cases, {lit['overview'].get('total_battles', '?')} battles")
    print(f"  Non-compliance: {len(nc['cases'])} cases, {len(nc['overlap_judges'])} overlap judges")


if __name__ == "__main__":
    main()
