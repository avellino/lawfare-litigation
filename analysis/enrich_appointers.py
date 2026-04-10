#!/usr/bin/env python3
"""
Enrich non-compliance judges with appointing president data.

For judges in the non-compliance dataset who are NOT already in the litigation
tracker (and thus don't have appointer info), look them up via:
  1. CourtListener People/Positions API
  2. FJC Biographical Database (fallback)

Reads:  data/judges_crossref.json
Writes: data/judges_crossref.json (updated with appointed_by for all judges)

Requires: COURTLISTENER_TOKEN in environment or ../.env
"""

import csv
import json
import logging
import os
import re
import sys
import time
import unicodedata
import hashlib
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv

# ── Configuration ──
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
CACHE_DIR = DATA_DIR / "cache"
CROSSREF_PATH = DATA_DIR / "judges_crossref.json"
FJC_CSV_PATH = DATA_DIR / "fjc_judges.csv"
FJC_DOWNLOAD_URL = "https://www.fjc.gov/sites/default/files/history/judges.csv"

COURTLISTENER_BASE_URL = "https://www.courtlistener.com/api/rest/v4"

# Load .env from parent project or current project
load_dotenv(BASE_DIR.parent / ".env")
load_dotenv(BASE_DIR / ".env")
COURTLISTENER_TOKEN = os.getenv("COURTLISTENER_TOKEN")

REQUEST_DELAY = 1.0  # seconds between API calls

CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Cache president names by position URL
_president_cache: dict[str, Optional[str]] = {}

NAME_SUFFIXES = {"jr.", "jr", "sr.", "sr", "ii", "iii", "iv", "v"}

KNOWN_PRESIDENTS = {
    "Barack Obama", "Donald Trump", "Joe Biden", "George W. Bush",
    "Bill Clinton", "Ronald Reagan", "George H.W. Bush", "Jimmy Carter",
    "Richard Nixon", "Lyndon B. Johnson", "Gerald Ford", "John F. Kennedy",
    "Dwight D. Eisenhower", "Harry S. Truman", "Franklin D. Roosevelt",
}

PRESIDENT_NAME_MAP = {
    "barack hussein obama": "Barack Obama",
    "barack obama": "Barack Obama",
    "donald john trump": "Donald Trump",
    "donald j. trump": "Donald Trump",
    "donald trump": "Donald Trump",
    "joseph robinette biden": "Joe Biden",
    "joseph r. biden": "Joe Biden",
    "joseph biden": "Joe Biden",
    "joe biden": "Joe Biden",
    "george w. bush": "George W. Bush",
    "george walker bush": "George W. Bush",
    "george h.w. bush": "George H.W. Bush",
    "george herbert walker bush": "George H.W. Bush",
    "william jefferson clinton": "Bill Clinton",
    "william j. clinton": "Bill Clinton",
    "william clinton": "Bill Clinton",
    "bill clinton": "Bill Clinton",
    "ronald wilson reagan": "Ronald Reagan",
    "ronald reagan": "Ronald Reagan",
    "james earl carter": "Jimmy Carter",
    "james carter": "Jimmy Carter",
    "jimmy carter": "Jimmy Carter",
    "richard milhous nixon": "Richard Nixon",
    "richard m. nixon": "Richard Nixon",
    "richard nixon": "Richard Nixon",
    "lyndon baines johnson": "Lyndon B. Johnson",
    "lyndon b. johnson": "Lyndon B. Johnson",
    "lyndon johnson": "Lyndon B. Johnson",
    "gerald rudolph ford": "Gerald Ford",
    "gerald r. ford": "Gerald Ford",
    "gerald ford": "Gerald Ford",
    "john fitzgerald kennedy": "John F. Kennedy",
    "john f. kennedy": "John F. Kennedy",
    "john kennedy": "John F. Kennedy",
    "dwight david eisenhower": "Dwight D. Eisenhower",
    "dwight d. eisenhower": "Dwight D. Eisenhower",
    "dwight eisenhower": "Dwight D. Eisenhower",
    "harry s. truman": "Harry S. Truman",
    "harry truman": "Harry S. Truman",
    "franklin d. roosevelt": "Franklin D. Roosevelt",
    "franklin delano roosevelt": "Franklin D. Roosevelt",
}


def normalize_president_name(name: str) -> str:
    lower = name.lower().strip()
    if lower in PRESIDENT_NAME_MAP:
        return PRESIDENT_NAME_MAP[lower]
    if lower == "george bush":
        return "George W. Bush"
    for key, val in PRESIDENT_NAME_MAP.items():
        if key in lower or lower in key:
            return val
    return name


def is_known_president(name: str) -> bool:
    return name in KNOWN_PRESIDENTS


# ── API helpers ──

def get_cache_key(endpoint: str, params: dict) -> str:
    key_str = endpoint + "|" + json.dumps(params, sort_keys=True)
    return hashlib.md5(key_str.encode()).hexdigest()


def make_api_call(endpoint: str, params: Optional[dict] = None) -> Optional[dict]:
    if not COURTLISTENER_TOKEN:
        logger.error("COURTLISTENER_TOKEN not set")
        return None

    cache_key = get_cache_key(endpoint, params or {})
    cache_path = CACHE_DIR / f"{cache_key}.json"
    if cache_path.exists():
        with open(cache_path) as f:
            return json.load(f)

    url = f"{COURTLISTENER_BASE_URL}/{endpoint}"
    headers = {"Authorization": f"Token {COURTLISTENER_TOKEN}"}

    try:
        time.sleep(REQUEST_DELAY)
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        with open(cache_path, "w") as f:
            json.dump(data, f, indent=2, default=str)
        return data
    except requests.exceptions.RequestException as e:
        logger.error(f"API call to {endpoint}: {e}")
        return None


# ── CourtListener lookup ──

def parse_judge_name(judge_name: str) -> tuple[str, str, str]:
    parts = judge_name.strip().split()
    if len(parts) < 2:
        return ("", "", judge_name.strip())
    if len(parts) == 2:
        return (parts[0], "", parts[1])
    if len(parts) == 3:
        return (parts[0], parts[1], parts[2])
    return (parts[0], " ".join(parts[1:-1]), parts[-1])


def find_person_via_search(judge_name: str) -> Optional[dict]:
    first, middle, last = parse_judge_name(judge_name)
    if not last:
        return None

    # Strip suffixes for search
    if last.lower().rstrip('.') in NAME_SUFFIXES:
        parts = judge_name.strip().split()
        if len(parts) >= 3:
            last = parts[-2]

    params = {"name_last": last}
    if first:
        params["name_first"] = first

    data = make_api_call("people/", params)
    if not data or not data.get("results"):
        if first:
            data = make_api_call("people/", {"name_last": last})

    if not data or not data.get("results"):
        return None

    results = data["results"]
    if len(results) == 1:
        return results[0]

    first_lower = first.lower() if first else ""
    for r in results:
        r_first = (r.get("name_first") or "").lower()
        if r_first == first_lower:
            return r
        if first_lower and r_first.startswith(first_lower[:3]):
            return r

    return None


def get_person_positions(person_url: str) -> list[dict]:
    match = re.search(r'/people/(\d+)/', person_url)
    if not match:
        return []
    person_id = match.group(1)
    data = make_api_call("positions/", {"person": person_id})
    if not data or not data.get("results"):
        return []
    return data["results"]


def is_likely_federal(pos: dict) -> bool:
    court = pos.get("court")
    if isinstance(court, dict):
        jurisdiction = (court.get("jurisdiction") or "").upper()
        if jurisdiction in ("FD", "FB", "F"):
            return True
        if jurisdiction.startswith("S"):
            return False
        court_url = court.get("resource_uri", "")
        if "/courts/scotus/" in court_url:
            return True
        if re.search(r'/courts/ca\d+/', court_url) or "/courts/cadc/" in court_url or "/courts/cafc/" in court_url:
            return True
        return False
    elif isinstance(court, str):
        if "/courts/scotus/" in court.lower():
            return True
        if re.search(r'/courts/ca\d+/', court.lower()) or "/courts/cadc/" in court.lower():
            return True
        if re.search(r'/courts/\w{2,4}d/', court.lower()):
            return True
    return False


def find_judicial_position(positions: list[dict]) -> Optional[dict]:
    federal_with_appointer = []
    other_with_appointer = []

    for pos in positions:
        has_appointer = bool(pos.get("appointer"))
        is_fed = is_likely_federal(pos)
        if is_fed and has_appointer:
            federal_with_appointer.append(pos)
        elif has_appointer:
            other_with_appointer.append(pos)

    candidates = federal_with_appointer or other_with_appointer
    if not candidates:
        return None
    return candidates[-1]


def resolve_appointer(appointer_url: str) -> Optional[str]:
    if appointer_url in _president_cache:
        return _president_cache[appointer_url]

    match = re.search(r'/positions/(\d+)/', appointer_url)
    if not match:
        return None

    pos_id = match.group(1)
    data = make_api_call(f"positions/{pos_id}/")
    if not data:
        return None

    def _extract_name(pdata: dict) -> Optional[str]:
        parts = [pdata.get("name_first", ""), pdata.get("name_middle", ""), pdata.get("name_last", "")]
        parts = [p for p in parts if p]
        return " ".join(parts) if parts else None

    person = data.get("person", {})
    if isinstance(person, dict):
        name = _extract_name(person)
        _president_cache[appointer_url] = name
        return name
    elif isinstance(person, str):
        pmatch = re.search(r'/people/(\d+)/', person)
        if pmatch:
            pdata = make_api_call(f"people/{pmatch.group(1)}/")
            if pdata:
                name = _extract_name(pdata)
                _president_cache[appointer_url] = name
                return name

    _president_cache[appointer_url] = None
    return None


def lookup_judge_appointer_cl(judge_name: str) -> Optional[str]:
    """Look up appointer via CourtListener API."""
    person = find_person_via_search(judge_name)
    if not person:
        return None

    person_id = person.get("id")
    person_url = f"https://www.courtlistener.com/api/rest/v4/people/{person_id}/"
    logger.info(f"  Found person via search: {person.get('name_first')} {person.get('name_last')} (id={person_id})")

    pos_urls = person.get("positions", [])
    if pos_urls and isinstance(pos_urls[0], str):
        positions = get_person_positions(person_url)
    elif pos_urls and isinstance(pos_urls[0], dict):
        positions = pos_urls
    else:
        positions = get_person_positions(person_url)

    if not positions:
        return None

    jud_pos = find_judicial_position(positions)
    if not jud_pos or not jud_pos.get("appointer"):
        return None

    president = resolve_appointer(jud_pos["appointer"])
    if president:
        normalized = normalize_president_name(president)
        if is_known_president(normalized):
            return normalized
        logger.info(f"  Non-presidential appointer: {president}")

    return None


# ── FJC Fallback ──

class FJCLookup:
    def __init__(self, csv_path: Path = FJC_CSV_PATH):
        self._lookup: dict[tuple[str, str], str] = {}
        self._lookup_normalized: dict[tuple[str, str], str] = {}
        self._loaded = False
        self._csv_path = csv_path

    def _ensure_loaded(self) -> bool:
        if self._loaded:
            return bool(self._lookup)

        if not self._csv_path.exists():
            logger.info("FJC CSV not found, attempting download...")
            if not self._download():
                logger.warning("FJC CSV unavailable — FJC fallback disabled")
                self._loaded = True
                return False

        try:
            with open(self._csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    last = row.get('Last Name', '').strip()
                    first = row.get('First Name', '').strip()
                    if not last or not first:
                        continue
                    president = None
                    for i in range(1, 7):
                        p = row.get(f'Appointing President ({i})', '').strip()
                        if p:
                            president = p
                    if president:
                        self._lookup[(last.lower(), first.lower())] = president
                        norm_last = self._normalize(last)
                        norm_first = self._normalize(first)
                        self._lookup_normalized[(norm_last, norm_first)] = president

            self._loaded = True
            logger.info(f"Loaded {len(self._lookup)} judges from FJC database")
            return True
        except Exception as e:
            logger.error(f"Loading FJC CSV: {e}")
            self._loaded = True
            return False

    def _download(self) -> bool:
        try:
            import urllib.request
            logger.info(f"Downloading FJC judges CSV...")
            urllib.request.urlretrieve(FJC_DOWNLOAD_URL, self._csv_path)
            logger.info("Download complete.")
            return True
        except Exception as e:
            logger.error(f"Downloading FJC CSV: {e}")
            return False

    @staticmethod
    def _normalize(name: str) -> str:
        nfkd = unicodedata.normalize('NFKD', name)
        ascii_name = ''.join(c for c in nfkd if not unicodedata.combining(c))
        ascii_name = re.sub(r"['\-.]", "", ascii_name)
        return re.sub(r'\s+', ' ', ascii_name).strip().lower()

    def find_president(self, judge_name: str) -> Optional[str]:
        if not self._ensure_loaded():
            return None

        parts = judge_name.strip().split()
        if len(parts) < 2:
            return None

        first = parts[0].lower()
        last = parts[-1].lower()

        if last in NAME_SUFFIXES and len(parts) >= 3:
            last = parts[-2].lower().rstrip('.')

        # Exact match
        result = self._lookup.get((last, first))
        if result:
            return result

        # Try middle name as first
        if len(parts) >= 3:
            middle = parts[1].lower().rstrip('.')
            result = self._lookup.get((last, middle))
            if result:
                return result

        # Normalized match
        norm_last = self._normalize(last)
        norm_first = self._normalize(first)
        result = self._lookup_normalized.get((norm_last, norm_first))
        if result:
            return result

        # Prefix match
        if len(first) >= 3:
            for (l, f), pres in self._lookup.items():
                if l == last and (f.startswith(first[:3]) or first.startswith(f[:3])):
                    return pres
            for (l, f), pres in self._lookup_normalized.items():
                if l == norm_last and (f.startswith(norm_first[:3]) or norm_first.startswith(f[:3])):
                    return pres

        return None


_fjc = FJCLookup()


# ── Main ──

def main():
    logger.info("=== Enriching non-compliance judges with appointer data ===")

    if not COURTLISTENER_TOKEN:
        logger.warning("No COURTLISTENER_TOKEN found — will rely on FJC database only")

    with open(CROSSREF_PATH) as f:
        crossref = json.load(f)

    judges = crossref["judges"]
    nc_only = crossref["nc_only_judges"]

    # Also process overlap judges that might be missing appointed_by
    to_process = []
    for name in judges:
        j = judges[name]
        if not j.get("appointed_by"):
            to_process.append(name)

    logger.info(f"Judges needing enrichment: {len(to_process)}")
    logger.info(f"  (of which {len([n for n in to_process if n in nc_only])} are non-compliance only)")

    found = 0
    not_found = 0

    for i, name in enumerate(to_process):
        logger.info(f"[{i+1}/{len(to_process)}] Looking up: {name}")

        # Try CourtListener first
        president = None
        if COURTLISTENER_TOKEN:
            president = lookup_judge_appointer_cl(name)

        # Fallback to FJC
        if not president:
            logger.info(f"  Trying FJC database...")
            fjc_result = _fjc.find_president(name)
            if fjc_result:
                president = normalize_president_name(fjc_result)
                if is_known_president(president):
                    logger.info(f"  Found via FJC: {president}")
                else:
                    logger.info(f"  FJC returned non-presidential: {fjc_result}")
                    president = None

        if president:
            judges[name]["appointed_by"] = president
            found += 1
            logger.info(f"  ✓ {name} → {president}")
        else:
            not_found += 1
            logger.warning(f"  ✗ {name} → NOT FOUND")

    # Save updated crossref
    with open(CROSSREF_PATH, "w") as f:
        json.dump(crossref, f, indent=2)

    logger.info(f"\n=== Summary ===")
    logger.info(f"  Processed: {len(to_process)}")
    logger.info(f"  Found: {found}")
    logger.info(f"  Not found: {not_found}")

    # Show full coverage
    total_with = sum(1 for j in judges.values() if j.get("appointed_by"))
    total = len(judges)
    logger.info(f"  Total judges with appointer: {total_with}/{total} ({total_with/total*100:.0f}%)")

    # President distribution across ALL judges
    from collections import Counter
    dist = Counter()
    case_dist = Counter()
    for name, j in judges.items():
        appt = j.get("appointed_by")
        if appt:
            dist[appt] += 1
            case_dist[appt] += j["nc_case_count"]

    logger.info(f"\n  Appointer distribution (judges):")
    for pres, count in dist.most_common():
        logger.info(f"    {pres:20s}: {count} judges, {case_dist[pres]} non-compliance cases")


if __name__ == "__main__":
    main()
