#!/usr/bin/env python3
"""
CNN 2024 Speaker Normalization

Reads parsed_cnn_2024.csv, applies speaker_aliases.csv,
removes transcription noise [APPLAUSE]/(CHEERS), 
and outputs normalized_cnn_2024.csv.
"""

import csv
import re
from collections import defaultdict, Counter
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────

INPUT_CSV  = Path("data/processed/parsed/parsed_cnn_2024.csv")
ALIAS_CSV  = Path("data/reference/speaker_aliases.csv")
OUTPUT_CSV = Path("data/processed/normalized/normalized_cnn_2024.csv")

FIELDNAMES = [
    "speaker", "party", "year", "night", "timestamp",
    "text", "word_count", "source_file", "source",
]

# ── Cleaning Logic ────────────────────────────────────────────────────────────

def clean_transcript_text(text):
    """
    Removes stage directions, bracketed noise, and transcription markers.
    Preserves 401(k) by checking for a digit before the parenthesis.
    """
    if not text or not isinstance(text, str):
        return ""
    
    # 1. Remove bracketed noise [APPLAUSE]
    cleaned = re.sub(r"\[.*?\]", " ", text)
    
    # 2. Remove parenthesized spans (CHEERS, sp?, ph, etc)
    # Negative lookbehind (?<!\d) preserves (k) in 401(k)
    cleaned = re.sub(r"(?<!\d)\([^)]*\)", " ", cleaned)
    
    # 3. Collapse whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    
    return cleaned

# ── Alias loader ──────────────────────────────────────────────────────────────

def load_aliases(filepath: Path) -> dict[str, str]:
    aliases = {}
    if not filepath.exists():
        return aliases
    with open(filepath, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            alias     = (row.get("alias") or "").strip()
            canonical = (row.get("canonical") or "").strip()
            if not alias or alias.startswith("#") or not canonical:
                continue
            aliases[alias] = canonical
    return aliases

# ── Dedup Logic ───────────────────────────────────────────────────────────────

def dedup_keep_longest(rows):
    """Keep only one row per speaker per night, selecting the one with most text."""
    unique_rows = {}
    for row in rows:
        key = (row["speaker"], row["night"])
        if key not in unique_rows or len(row["text"]) > len(unique_rows[key]["text"]):
            unique_rows[key] = row
    return list(unique_rows.values())

# ── Main Normalizer ───────────────────────────────────────────────────────────

def process_cnn_normalization():
    aliases = load_aliases(ALIAS_CSV)
    rows = []
    excluded = 0
    renamed = 0

    if not INPUT_CSV.exists():
        print(f"Error: {INPUT_CSV} not found.")
        return

    with open(INPUT_CSV, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_name = row["speaker"].strip()
            
            # Apply Aliases
            if raw_name in aliases:
                normalized = aliases[raw_name]
                if normalized.upper() == "EXCLUDE":
                    excluded += 1
                    continue
                renamed += 1
            else:
                normalized = raw_name

            # CLEAN THE TEXT AND RECOMPUTE WORD COUNT
            raw_text = row.get("text", "")
            clean_text = clean_transcript_text(raw_text)
            
            row["speaker"] = normalized
            row["text"] = clean_text
            row["word_count"] = len(clean_text.split())
            
            rows.append({k: row.get(k, "") for k in FIELDNAMES})

    # Dedup — same speaker + same night, keep longest
    before_dedup = len(rows)
    rows = dedup_keep_longest(rows)
    deduped_count = before_dedup - len(rows)

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nSource: {INPUT_CSV}")
    print(f"  Input rows: {before_dedup + excluded}")
    print(f"  Excluded:   {excluded}")
    print(f"  Deduped:    {deduped_count}")
    print(f"  Final:      {len(rows)} clean rows → {OUTPUT_CSV}")

if __name__ == "__main__":
    process_cnn_normalization()