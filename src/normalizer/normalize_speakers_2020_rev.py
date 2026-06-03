#!/usr/bin/env python3
"""
Rev 2020 Speaker Normalization

Reads parsed_rev_2020.csv, applies aliases_rev_2020.csv,
aggregates fragmented rows by speaker+night, and outputs
normalized_rev_2020.csv.

Key differences from 2024 normalizer:
  - Ghost party exclusions checked by name AND party
  - Aggregation step concatenates fragmented rows in timestamp order
"""

import csv
import re
from collections import defaultdict, Counter
from pathlib import Path


# ── Paths ─────────────────────────────────────────────────────────────────────

INPUT_CSV  = Path("data/processed/parsed/parsed_rev_2020.csv")
ALIAS_CSV  = Path("data/reference/aliases_rev_2020.csv")
OUTPUT_CSV = Path("data/processed/normalized/normalized_rev_2020.csv")

FIELDNAMES = [
    "speaker", "party", "year", "night", "timestamp",
    "speech", "word_count", "source_file", "source",
]


# ── Alias loader ──────────────────────────────────────────────────────────────

def load_aliases(filepath: Path) -> dict[tuple, str]:
    """
    Load aliases from CSV.
    Returns dict of (alias, party) -> canonical.
    Party 'Both' matches any party.
    Skips comment rows and empty rows.
    """
    aliases = {}
    with open(filepath, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            alias     = (row.get("alias") or "").strip()
            canonical = (row.get("canonical") or "").strip()
            party     = (row.get("party") or "").strip()
            if not alias or alias.startswith("#") or not canonical:
                continue
            aliases[(alias, party)] = canonical
    return aliases


# ── Normalizer ────────────────────────────────────────────────────────────────

def normalize_speaker(name: str, party: str, aliases: dict[tuple, str]) -> str | None:
    """
    Normalize a speaker name using the alias file.
    Checks (name, party) first, then (name, Both) as fallback.

    Returns:
        None       → exclude this row
        name as-is → UNKNOWN, keep for manual review
        canonical  → corrected name
    """
    # Try exact match with party
    key = (name, party)
    if key in aliases:
        canonical = aliases[key]
        if canonical == "EXCLUDE":
            return None
        if canonical == "UNKNOWN":
            return name
        return canonical

    # Try Both
    key_both = (name, "Both")
    if key_both in aliases:
        canonical = aliases[key_both]
        if canonical == "EXCLUDE":
            return None
        if canonical == "UNKNOWN":
            return name
        return canonical

    # Case-insensitive fallback
    name_lower = name.lower()
    party_lower = party.lower()
    for (alias, alias_party), canonical in aliases.items():
        if alias.lower() == name_lower:
            if alias_party.lower() == party_lower or alias_party == "Both":
                if canonical == "EXCLUDE":
                    return None
                if canonical == "UNKNOWN":
                    return name
                return canonical

    return name


# ── Aggregation ───────────────────────────────────────────────────────────────

def parse_timestamp(ts: str) -> tuple[int, int, int]:
    """Parse HH:MM:SS or MM:SS timestamp into sortable tuple."""
    parts = ts.strip().split(":")
    try:
        if len(parts) == 3:
            return int(parts[0]), int(parts[1]), int(parts[2])
        elif len(parts) == 2:
            return 0, int(parts[0]), int(parts[1])
    except ValueError:
        pass
    return 0, 0, 0


def aggregate_rows(rows: list[dict]) -> list[dict]:
    """
    Group rows by (speaker, party, year, night) and concatenate
    text in timestamp order. Sum word counts.

    Rows with the same speaker on different nights are kept separate.
    """
    groups: dict[tuple, list[dict]] = defaultdict(list)

    for row in rows:
        key = (row["speaker"], row["party"], row["year"], row["night"])
        groups[key].append(row)

    result = []
    for key, group in groups.items():
        if len(group) == 1:
            result.append(group[0])
            continue

        # Sort by timestamp
        group.sort(key=lambda r: parse_timestamp(r.get("timestamp", "")))

        # Concatenate speech
        combined_text = " ".join(r["speech"] for r in group if r["speech"].strip())
        total_words   = sum(int(r["word_count"]) for r in group)
        first         = group[0]

        merged = {
            "speaker":     first["speaker"],
            "party":       first["party"],
            "year":        first["year"],
            "night":       first["night"],
            "timestamp":   first["timestamp"],
            "speech":      combined_text,
            "word_count":  total_words,
            "source_file": first["source_file"],
            "source":      first["source"],
        }
        result.append(merged)

    return result


# ── Main ──────────────────────────────────────────────────────────────────────

def normalize_rev_2020(
    input_path: Path  = INPUT_CSV,
    alias_path: Path  = ALIAS_CSV,
    output_path: Path = OUTPUT_CSV,
) -> list[dict]:

    aliases = load_aliases(alias_path)
    print(f"Loaded {len(aliases)} aliases from {alias_path}")

    rows     = []
    excluded = 0
    renamed  = 0

    with open(input_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            original = row["speaker"]
            party    = row["party"]
            normalized = normalize_speaker(original, party, aliases)

            if normalized is None:
                excluded += 1
                continue

            if normalized != original:
                renamed += 1
                print(f"  RENAMED:  {original} ({party}) → {normalized}")

            row["speaker"] = normalized
            # Input CSV uses 'text'; output schema uses 'speech' — remap here
            row["speech"] = row.get("speech") or row.get("text", "")
            rows.append({k: row.get(k, "") for k in FIELDNAMES})

    print(f"\nAfter alias resolution: {len(rows)} rows ({excluded} excluded, {renamed} renamed)")

    # Drop known artifact rows (curly and straight apostrophe variants)
    ARTIFACT_SPEAKERS = {
        "We don't burn- Kimberly Guilfoyle",
        "We don\u2019t burn- Kimberly Guilfoyle",
    }
    before_artifact = len(rows)
    rows = [r for r in rows if r["speaker"] not in ARTIFACT_SPEAKERS]
    if len(rows) < before_artifact:
        print(f"Dropped {before_artifact - len(rows)} artifact row(s)")

    # Normalize curly apostrophes in speaker names so aggregation keys match
    for row in rows:
        row["speaker"] = row["speaker"].replace("\u2019", "'").replace("\u2018", "'")

    # Aggregate fragmented rows
    before = len(rows)
    rows = aggregate_rows(rows)
    print(f"After aggregation: {len(rows)} rows ({before - len(rows)} fragments merged)")

    # Drop empty speeches
    before_empty = len(rows)
    rows = [r for r in rows if r["speech"].strip()]
    if len(rows) < before_empty:
        print(f"Dropped {before_empty - len(rows)} empty speech row(s)")
        
    # Fix MM:SS timestamps to HH:MM:SS for Rev 2020
    for row in rows:
        if re.match(r'^\d{2}:\d{2}$', row.get('timestamp', '')):
            row['timestamp'] = '00:' + row['timestamp']


    # Sort by party (Democratic first), then night, then timestamp
    rows.sort(key=lambda x: (
        0 if x["party"] == "Democratic" else 1,
        int(x["night"]) if x["night"] else 0,
        parse_timestamp(x.get("timestamp", "")),
    ))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nOutput: {len(rows)} rows → {output_path}")

    by_party = Counter(r["party"] for r in rows)
    by_night = Counter(r["night"] for r in rows)

    print("\n=== By Party ===")
    for party, count in sorted(by_party.items()):
        print(f"  {party}: {count}")

    print("\n=== By Night ===")
    for night, count in sorted(by_night.items()):
        print(f"  Night {night}: {count}")

    return rows


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Normalize Rev 2020 parsed speeches")
    ap.add_argument("--input",   type=Path, default=INPUT_CSV)
    ap.add_argument("--aliases", type=Path, default=ALIAS_CSV)
    ap.add_argument("--output",  type=Path, default=OUTPUT_CSV)
    args = ap.parse_args()
    normalize_rev_2020(args.input, args.aliases, args.output)


if __name__ == "__main__":
    main()