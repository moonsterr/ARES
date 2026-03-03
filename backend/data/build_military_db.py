#!/usr/bin/env python3
"""
GeoNames Military Base Database Builder
========================================
Downloads GeoNames data for Middle East countries and extracts
military site records into mideast_military_bases.json.

Usage:
    cd backend/data/
    python build_military_db.py

This script supplements the manually-curated entries already in
mideast_military_bases.json with automated GeoNames data.

Prerequisites:
    pip install requests
"""
import csv
import json
import os
import sys
import zipfile
import io

try:
    import requests
except ImportError:
    print("Install requests: pip install requests")
    sys.exit(1)

MILITARY_CODES = {"AIRB", "MILB", "NAVB", "INSM", "RSTN", "BSTN", "AIRG", "AIRT"}
COUNTRIES = ["IL", "LB", "SY", "JO", "EG", "IR", "IQ", "SA", "YE", "TR", "AE", "KW", "BH", "QA", "OM", "PS"]

GEONAMES_URL = "http://download.geonames.org/export/dump/{cc}.zip"


def download_country(cc: str) -> list[dict]:
    """Download and parse GeoNames data for a country code."""
    url = GEONAMES_URL.format(cc=cc)
    print(f"Downloading {cc}...", end=" ", flush=True)
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        zf = zipfile.ZipFile(io.BytesIO(r.content))
        txt_name = f"{cc}.txt"
        if txt_name not in zf.namelist():
            print(f"SKIPPED (no {txt_name} in archive)")
            return []
        with zf.open(txt_name) as f:
            content = f.read().decode("utf-8")
    except Exception as e:
        print(f"FAILED ({e})")
        return []

    sites = []
    reader = csv.reader(io.StringIO(content), delimiter="\t")
    for row in reader:
        if len(row) < 10:
            continue
        feature_code = row[7]
        if feature_code not in MILITARY_CODES:
            continue
        try:
            lat = float(row[4])
            lon = float(row[5])
        except ValueError:
            continue

        alt_names = [n.strip() for n in row[3].split(",") if n.strip()]
        sites.append({
            "id":           f"{feature_code.lower()}_{cc.lower()}_{row[0]}",
            "canonical":    row[1],
            "lat":          lat,
            "lon":          lon,
            "country":      cc,
            "feature_code": feature_code,
            "alt_names":    alt_names[:10],  # cap alt names
        })
    print(f"OK ({len(sites)} military sites)")
    return sites


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(script_dir, "mideast_military_bases.json")

    # Load existing manually-curated data
    existing = []
    if os.path.exists(output_path):
        with open(output_path, encoding="utf-8") as f:
            existing = json.load(f)
        print(f"Loaded {len(existing)} existing manually-curated sites")

    # Build existing ID set to avoid duplicates
    existing_ids = {s["canonical"].lower() for s in existing}

    # Download and parse GeoNames data
    all_new_sites = []
    for cc in COUNTRIES:
        country_sites = download_country(cc)
        for site in country_sites:
            # Skip if canonical name already in our curated dataset
            if site["canonical"].lower() not in existing_ids:
                all_new_sites.append(site)
                existing_ids.add(site["canonical"].lower())

    combined = existing + all_new_sites
    print(f"\nTotal sites: {len(combined)} ({len(existing)} manual + {len(all_new_sites)} GeoNames)")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(combined, f, ensure_ascii=False, indent=2)
    print(f"Written to {output_path}")


if __name__ == "__main__":
    main()
