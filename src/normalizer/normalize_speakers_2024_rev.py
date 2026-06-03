#!/usr/bin/env python3
"""
Rev 2024 Speaker Normalization

Reads parsed_rev_2024.csv, applies speaker_aliases.csv,
and outputs normalized_rev_2024.csv.

Excludes junk speakers, fixes name variants, and flags unknowns.
"""

import csv
from collections import defaultdict, Counter
from pathlib import Path


# ── Paths ─────────────────────────────────────────────────────────────────────

INPUT_CSV  = Path("data/processed/parsed/parsed_rev_2024.csv")
ALIAS_CSV  = Path("data/reference/speaker_aliases.csv")
OUTPUT_CSV = Path("data/processed/normalized/normalized_rev_2024.csv")

FIELDNAMES = [
    "speaker", "party", "year", "night", "timestamp",
    "text", "word_count", "source_file", "source",
]


# ── Alias loader ──────────────────────────────────────────────────────────────

def load_aliases(filepath: Path) -> dict[str, str]:
    """
    Load speaker aliases from CSV.
    Returns dict of alias -> canonical.
    Skips comment rows (starting with #) and empty rows.
    """
    aliases = {}
    with open(filepath, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            alias     = (row.get("alias") or "").strip()
            canonical = (row.get("canonical") or "").strip()
            if not alias or alias.startswith("#") or not canonical:
                continue
            aliases[alias] = canonical
    return aliases


# ── Normalizer ────────────────────────────────────────────────────────────────

def normalize_speaker(name: str, aliases: dict[str, str]) -> str | None:
    """
    Normalize a speaker name using the alias file.

    Returns:
        None         → exclude this row entirely
        name as-is   → UNKNOWN, keep for manual review
        canonical    → corrected name
    """
    # Exact match
    if name in aliases:
        canonical = aliases[name]
        if canonical == "EXCLUDE":
            return None
        if canonical == "UNKNOWN":
            return name
        return canonical

    # Case-insensitive fallback
    name_lower = name.lower()
    for alias, canonical in aliases.items():
        if alias.lower() == name_lower:
            if canonical == "EXCLUDE":
                return None
            if canonical == "UNKNOWN":
                return name
            return canonical

    return name


# ── Dedup ─────────────────────────────────────────────────────────────────────

def dedup_keep_longest(rows: list[dict]) -> list[dict]:
    """
    For any speaker appearing more than once on the same night,
    keep the row with the most words and drop the shorter one.

    Handles cases where two different raw names resolved to the same
    canonical name via the alias file.

    Speakers appearing on different nights are NOT affected.
    """
    groups: dict[tuple, list[dict]] = defaultdict(list)

    for row in rows:
        key = (row["speaker"], row["party"], row["year"], row["night"])
        groups[key].append(row)

    result = []
    for key, group in groups.items():
        if len(group) == 1:
            result.append(group[0])
        else:
            longest = max(group, key=lambda r: int(r["word_count"]))
            dropped = [r for r in group if r is not longest]
            for d in dropped:
                print(f"  DEDUP:    kept '{longest['source_file']}' "
                      f"({longest['word_count']} words), "
                      f"dropped '{d['source_file']}' ({d['word_count']} words)")
            result.append(longest)

    return result


# ── Main ──────────────────────────────────────────────────────────────────────

def normalize_rev_2024(
    input_path: Path  = INPUT_CSV,
    alias_path: Path  = ALIAS_CSV,
    output_path: Path = OUTPUT_CSV,
) -> list[dict]:

    aliases = load_aliases(alias_path)
    print(f"Loaded {len(aliases)} aliases from {alias_path}")

    rows = []
    excluded = 0
    renamed  = 0

    with open(input_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            original = row["speaker"]
            normalized = normalize_speaker(original, aliases)

            if normalized is None:
                excluded += 1
                print(f"  EXCLUDED: {original}")
                continue

            if normalized != original:
                renamed += 1
                print(f"  RENAMED:  {original} → {normalized}")

            row["speaker"] = normalized
            rows.append({k: row.get(k, "") for k in FIELDNAMES})

    # Dedup — same speaker + same night, keep longest
    before = len(rows)
    rows = dedup_keep_longest(rows)
    deduped = before - len(rows)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nInput:    {before + excluded} rows")
    print(f"Excluded: {excluded}")
    print(f"Renamed:  {renamed}")
    print(f"Deduped:  {deduped}")
    print(f"Output:   {len(rows)} rows → {output_path}")

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
    ap = argparse.ArgumentParser(description="Normalize Rev 2024 parsed speeches")
    ap.add_argument("--input",   type=Path, default=INPUT_CSV)
    ap.add_argument("--aliases", type=Path, default=ALIAS_CSV)
    ap.add_argument("--output",  type=Path, default=OUTPUT_CSV)
    args = ap.parse_args()
    normalize_rev_2024(args.input, args.aliases, args.output)


if __name__ == "__main__":
    main()