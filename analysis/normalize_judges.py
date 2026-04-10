"""
Normalize judge names in the non-compliance dataset and cross-reference
with the litigation tracker database.

Problems in the raw data:
1. Varying prefixes: "U.S. District Judge", "U.S. Senior District Judge",
   "U.S. District Chief Judge", "U.S. Magistrate Judge", etc.
2. Typos: "Schlitz" vs "Schiltz", "Provenzino" vs "Provinzino",
   "Distrct" vs "District", "DIstrict", missing periods
3. Same judge, different name forms: "Zahid N. Quraishi" vs "Zahid Nisar Quraishi",
   "Katharine S. Hayden" vs "Katharine Sweeney Hayden",
   "Renee M. Bumb" vs "Renee Marie Bumb"
4. Suffixes: "of the Western District of Missouri"
5. Unicode: "Martínez-Olguín" vs "Martinez-Olguin", "Saldaña"
"""

import json
import re
import sqlite3
import unicodedata
from collections import Counter, defaultdict

# ── Manual merge map: maps variant → canonical name ──
# Canonical names match the litigation tracker format (no prefix, no title)
MERGE_MAP = {
    # Typos / misspellings
    "Patrick J. Schlitz": "Patrick J. Schiltz",
    "Laura M. Provenzino": "Laura M. Provinzino",
    "Laura M Provinzino": "Laura M. Provinzino",   # missing period
    "Michael J. David": "Michael J. Davis",

    # Full middle name vs initial
    "Zahid Nisar Quraishi": "Zahid N. Quraishi",
    "Katharine Sweeney Hayden": "Katharine S. Hayden",
    "Renee Marie Bumb": "Renee M. Bumb",

    # Missing middle initial (non-compliance vs litigation tracker)
    "James Boasberg": "James E. Boasberg",

    # Unicode normalization (handled automatically too, but explicit for clarity)
    "Araceli Martínez-Olguín": "Araceli Martinez-Olguin",
    "Diana Saldaña": "Diana Saldana",
}


def strip_prefix(name: str) -> str:
    """Remove judicial title prefixes and suffixes."""
    # Remove suffix like "of the Western District of Missouri"
    name = re.sub(r'\s+of the\s+.*$', '', name)

    # Remove all known prefixes (order matters — longer first)
    prefixes = [
        r'U\.S\.\s+District\s+Chief\s+Judge\s+',
        r'U\.S\.\s+Senior\s+District\s+Judge\s+',
        r'U\.S\.\s+Visiting\s+District\s+Judge\s+',
        r'U\.S\.\s+Magistrate\s+Judge\s+',
        r'U\.S\.\s+District\s+Judge\.?\s+',    # handles "Judge." typo
        r'U\.S\.\s+DIstrict\s+Judge\s+',       # handles casing typo
        r'U\.S\.\s+Distrct\s+Judge\s+',        # handles spelling typo
        r'U\.S\.\s+District\s+',               # "U.S. District Kathleen Cardone"
        r'U\.S\s+District\s+Judge\s+',         # missing period after "U.S"
        r'Chief\s+U\.S\.\s+District\s+Judge\s+',
        r'Senior\s+U\.S\.\s+District\s+Judge\s+',
    ]
    for prefix in prefixes:
        name = re.sub('^' + prefix, '', name, flags=re.IGNORECASE)

    return name.strip()


def normalize_unicode(name: str) -> str:
    """Normalize accented characters to ASCII equivalents."""
    # NFD decomposition then strip combining marks
    nfkd = unicodedata.normalize('NFKD', name)
    return ''.join(c for c in nfkd if not unicodedata.category(c).startswith('M'))


def normalize_judge_name(raw_name: str) -> str:
    """Full normalization pipeline for a judge name."""
    name = raw_name.strip()
    name = strip_prefix(name)
    name = normalize_unicode(name)

    # Apply manual merge map
    if name in MERGE_MAP:
        name = MERGE_MAP[name]

    return name


def extract_judge_type(raw_name: str) -> str:
    """Extract whether this is a District, Senior, Magistrate, etc. judge."""
    raw = raw_name.strip().lower()
    if 'magistrate' in raw:
        return 'Magistrate'
    if 'senior' in raw:
        return 'Senior'
    if 'chief' in raw:
        return 'Chief'
    if 'visiting' in raw:
        return 'Visiting'
    return 'District'


def main():
    # ── Load non-compliance data ──
    with open('data/mega_list.json') as f:
        data = json.load(f)
    rows = data['values']
    headers = rows[0]

    # ── Load litigation tracker judges ──
    conn = sqlite3.connect('data/litigation_tracker.db')
    cur = conn.cursor()
    cur.execute('''
        SELECT judge_name, appointed_by, court, executive_action,
               case_name, docket_number, status, battle_id,
               COUNT(*) OVER (PARTITION BY judge_name) as judge_case_count
        FROM cases
        WHERE judge_name IS NOT NULL
    ''')
    lit_rows = cur.fetchall()

    # Build judge lookup: normalized name → info
    lit_judge_info = {}
    lit_judge_cases = defaultdict(list)
    for row in lit_rows:
        name_norm = normalize_unicode(row[0].strip())
        if name_norm not in lit_judge_info:
            lit_judge_info[name_norm] = {
                'appointed_by': row[1],
                'court': row[2],
                'lit_case_count': row[8],
            }
        lit_judge_cases[name_norm].append({
            'case_name': row[4],
            'docket_number': row[5],
            'executive_action': row[3],
            'status': row[6],
            'battle_id': row[7],
        })

    # ── Normalize non-compliance judges ──
    nc_by_judge = defaultdict(list)
    normalization_log = []

    for i, r in enumerate(rows[1:], start=1):
        if len(r) <= 5 or not r[5]:
            continue

        raw = r[5].strip()
        normalized = normalize_judge_name(raw)
        judge_type = extract_judge_type(raw)

        if raw != f"U.S. District Judge {normalized}":
            normalization_log.append((raw, normalized))

        case_info = {
            'row_index': i,
            'case_name': r[0] if len(r) > 0 else '',
            'case_no': r[1] if len(r) > 1 else '',
            'jurisdiction': r[2] if len(r) > 2 else '',
            'date': r[3] if len(r) > 3 else '',
            'violation_types': r[9] if len(r) > 9 else '',
            'egregious': r[10] if len(r) > 10 else '',
            'judge_type': judge_type,
            'raw_judge_name': raw,
        }
        nc_by_judge[normalized].append(case_info)

    # ── Report ──
    print("=" * 70)
    print("NORMALIZATION RESULTS")
    print("=" * 70)

    # Show non-trivial normalizations
    print(f"\nNon-trivial normalizations applied:")
    seen = set()
    for raw, norm in sorted(normalization_log):
        key = (raw, norm)
        if key not in seen:
            seen.add(key)
            # Only show interesting ones (not just prefix stripping)
            stripped = strip_prefix(raw)
            if stripped != norm or 'Magistrate' in raw or 'Senior' in raw or 'Chief' in raw or 'Visiting' in raw:
                print(f'  "{raw}"')
                print(f'    → "{norm}"')

    nc_judges = {name: len(cases) for name, cases in nc_by_judge.items()}

    print(f"\nUnique judges after normalization: {len(nc_judges)} (was ~90 before)")

    # ── Cross-reference ──
    overlap = {}
    nc_only = {}
    lit_only = {}

    for name, count in sorted(nc_judges.items(), key=lambda x: -x[1]):
        if name in lit_judge_info:
            overlap[name] = {
                'nc_cases': count,
                'lit_cases': lit_judge_info[name]['lit_case_count'],
                'appointed_by': lit_judge_info[name]['appointed_by'],
                'court': lit_judge_info[name]['court'],
            }
        else:
            nc_only[name] = count

    for name, info in lit_judge_info.items():
        if name not in nc_judges:
            lit_only[name] = info

    print(f"\n{'=' * 70}")
    print(f"CROSS-REFERENCE RESULTS")
    print(f"{'=' * 70}")
    print(f"\n  Judges in BOTH datasets:           {len(overlap)}")
    print(f"  Judges in non-compliance only:     {len(nc_only)}")
    print(f"  Judges in litigation tracker only:  {len(lit_only)}")

    print(f"\n── JUDGES IN BOTH DATASETS ──\n")
    for name, info in sorted(overlap.items(), key=lambda x: -(x[1]['nc_cases'] + x[1]['lit_cases'])):
        print(f"  {name}")
        print(f"    Non-compliance: {info['nc_cases']} cases  |  Structural litigation: {info['lit_cases']} cases")
        print(f"    Appointed by: {info['appointed_by'] or 'unknown'}")
        print()

    print(f"\n── NON-COMPLIANCE ONLY (need enrichment) ──\n")
    for name, count in sorted(nc_only.items(), key=lambda x: -x[1]):
        print(f"  {count:3d} cases  |  {name}")

    # ── Write output JSON for downstream use ──
    output = {
        'judges': {},
        'overlap_judges': list(overlap.keys()),
        'nc_only_judges': list(nc_only.keys()),
    }

    for name, cases in nc_by_judge.items():
        judge_data = {
            'normalized_name': name,
            'nc_cases': cases,
            'nc_case_count': len(cases),
            'in_litigation_tracker': name in lit_judge_info,
        }
        if name in lit_judge_info:
            judge_data['appointed_by'] = lit_judge_info[name]['appointed_by']
            judge_data['lit_case_count'] = lit_judge_info[name]['lit_case_count']
            judge_data['lit_cases'] = lit_judge_cases[name]
        output['judges'][name] = judge_data

    with open('data/judges_crossref.json', 'w') as f:
        json.dump(output, f, indent=2)
    print(f"\nWrote data/judges_crossref.json")

    # ── Summary stats ──
    print(f"\n{'=' * 70}")
    print(f"SUMMARY")
    print(f"{'=' * 70}")
    nc_cases_with_overlap = sum(info['nc_cases'] for info in overlap.values())
    total_nc = sum(nc_judges.values())
    print(f"  {nc_cases_with_overlap} of {total_nc} non-compliance cases ({nc_cases_with_overlap/total_nc*100:.0f}%) "
          f"are before judges who also handle structural litigation")

    # Appointing president breakdown for overlap judges
    appt_counts = Counter()
    for name, info in overlap.items():
        appt = info['appointed_by'] or 'Unknown'
        appt_counts[appt] += info['nc_cases']
    print(f"\n  Non-compliance cases before overlap judges, by appointing president:")
    for appt, count in appt_counts.most_common():
        print(f"    {appt:20s}: {count} cases")


if __name__ == '__main__':
    main()
