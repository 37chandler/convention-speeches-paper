#!/usr/bin/env python3
"""
unified_normalize_2024.py
-------------------------
A unified script to:
1. Normalize speaker names (Casing & Aliases)
2. Remove noise markers (APPLAUSE, CHEERS)
3. Strip all parenthesized content (stage directions) while preserving 401(k)
4. Tidy whitespace and re-capitalize sentence starts exposed by stripping.
"""

import csv
import re
import os
import sys
import pandas as pd
from pathlib import Path

# --- CONFIGURATION ---
CSPAN_FILE  = "data/processed/parsed/parsed_cspan_2024_check.csv"
ALIAS_FILE  = "data/reference/aliases_cspan_2024.csv"
OUTPUT_FILE = "data/processed/normalized/normalized_cspan_2024.csv"

# --- REGEX PATTERNS ---

# Match any parenthesized span that is NOT "401(k)"-style.
# Uses negative lookbehind on a digit to preserve (k) in 401(k).
_PAREN_SPAN = re.compile(r"(?<!\d)\([^)]*\)")

# Sentence-start capitalization pattern (to fix "...end. (Cheers) and then...")
_SENT_START = re.compile(r"([.!?])(\s+)([a-z])")

# Brackets and Music Noise
_NOISE_BRACKETS = re.compile(
    r"\[(?:APPLAUSE|CHEERS?|CHEERING|CLAPPING?|LAUGHTER|MUSIC|"
    r"INAUDIBLE|CROWD[^\]]{0,40}|PAUSE|CROSSTALK)[^\]]{0,40}\]"
    r"|♪+",
    re.IGNORECASE,
)

# --- FUNCTIONS ---

def fix_name_casing(name: str) -> str:
    """Standardize name casing (e.g., O'MALLEY -> O'Malley)."""
    if not name:
        return name
    if name != name.upper():
        return name

    titled = name.title()
    # Handle Mc/Mac/O'
    titled = re.sub(r"\b(Mc|Mac)([a-z])", lambda m: m.group(1).capitalize() + m.group(2).upper(), titled, flags=re.IGNORECASE)
    titled = re.sub(r"\bO'([a-z])", lambda m: "O'" + m.group(1).upper(), titled)
    # Handle Jr/Sr
    titled = re.sub(r"\bJr\b\.?", "Jr.", titled)
    titled = re.sub(r"\bSr\b\.?", "Sr.", titled)
    return titled

def strip_and_clean_speech(text: str) -> str:
    """
    Combines paren-stripping, noise removal, and grammar tidy-up.
    """
    if not isinstance(text, str) or not text:
        return ""

    # 1. Remove bracketed noise [APPLAUSE]
    cleaned = _NOISE_BRACKETS.sub(" ", text)

    # 2. Remove parenthesized spans (except 401(k))
    cleaned = _PAREN_SPAN.sub("", cleaned)

    # 3. Tidy whitespace: " . " -> ". " and collapse multiple spaces
    cleaned = re.sub(r"\s+([,.!?;:])", r"\1", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = cleaned.strip()

    # 4. Re-capitalize sentence starts exposed by removals
    cleaned = _SENT_START.sub(
        lambda m: m.group(1) + m.group(2) + m.group(3).upper(),
        cleaned,
    )

    return cleaned

def load_aliases(path):
    aliases = {}
    excludes = set()
    if not Path(path).exists():
        print(f"WARNING: Alias file not found at {path}")
        return aliases, excludes
        
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            raw = row["raw_name"].strip().upper()
            action = row["action"].strip().lower()
            canon = row["canonical_name"].strip()

            if action == "fix":
                aliases[raw] = canon
            elif action == "exclude":
                excludes.add(raw)
    return aliases, excludes

def main():
    print(f"Loading aliases from: {ALIAS_FILE}")
    aliases, excludes = load_aliases(ALIAS_FILE)
    
    print(f"Loading C-SPAN data from: {CSPAN_FILE}")
    if not Path(CSPAN_FILE).exists():
        print(f"ERROR: Input file {CSPAN_FILE} not found.")
        return 1

    df = pd.read_csv(CSPAN_FILE)
    
    # Process speakers
    def get_canonical_name(name):
        name_upper = str(name).strip().upper()
        if name_upper in aliases:
            return aliases[name_upper]
        return fix_name_casing(str(name).strip())

    # Apply cleaning
    print("Cleaning speakers and stripping parentheticals from speech...")
    df['speaker'] = df['speaker'].apply(get_canonical_name)
    
    # Remove rows where speaker is in excludes set
    df = df[~df['speaker'].str.upper().isin(excludes)]

    # Clean the speech column
    # If your input CSV uses 'speech', use that; your script used both 'speech' and 'text'
    # Checking for column name existence:
    col = 'speech' if 'speech' in df.columns else 'text'
    
    df[col] = df[col].apply(strip_and_clean_speech)
    
    # Recalculate word counts after cleaning
    df['word_count'] = df[col].apply(lambda x: len(str(x).split()) if x else 0)

    # Save output
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8")

    print(f"Successfully processed {len(df)} rows.")
    print(f"Saved to -> {OUTPUT_FILE}")
    return 0

if __name__ == "__main__":
    sys.exit(main())