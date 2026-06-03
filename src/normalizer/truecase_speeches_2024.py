#!/usr/bin/env python3
"""
truecase_speeches_2024.py

truecaser for 2024 convention speeches.
"""

import pandas as pd
import re
import os
from pathlib import Path
import spacy

# -------------------------
# Load spaCy
# -------------------------
nlp = spacy.load("en_core_web_sm")

# -------------------------
# FILE PATHS
# -------------------------
INPUT_FILE = "data/processed/normalized/normalized_final_merged_2024.csv"
OUTPUT_FILE = "data/processed/normalized/truecased_final_merged_2024.csv"

# -------------------------
# ACRONYMS
# -------------------------
ACRONYMS = {
    "USA","DNC","RNC","GOP","FBI","CIA","NATO","UN","EU",
    "MAGA","IVF","COVID","LGBTQ","VP","POTUS","CEO",
    "AOC","MLK","JFK","DNA","TV","II","III","IV"
}

# -------------------------
# EXPANDED PROPER NOUNS
# FIX 3: Removed single-letter "B" and "J" — these caused
# partial-word corruption (e.g. "job" → "JoB"). Middle initials
# are already handled correctly by fix_middle_initials().
# -------------------------
PROPER_NOUNS = {
    "Barack","Donald","Joe","Kamala","Tim",
    "Biden","Trump","Harris","Walz","Vance",

    "Cory","Mitch","Vanessa","Peggy","Garlin",

    "Ida","Wells","Fannie","Shirley","Jackson","Jesse",

    "Marjorie","Taylor","Greene",
    "Lena","Hidalgo",

    # "B" and "J" removed — see note above

    "Chicago","Milwaukee","Mississippi",
    "Delaware","California","Long Beach",

    "Native","American",
    "Democrat","Democratic","Republican",

    "Congress","Senate","White House",

    "God","Jesus"
}

# -------------------------
# TITLES
# FIX 2: Multi-word titles added ("lieutenant governor").
# Sorting by length in fix_titles() ensures these match
# before their shorter sub-strings ("lieutenant", "president").
# -------------------------
TITLES = [
    "vice president",
    "lieutenant governor",
    "president",
    "governor",
    "senator",
    "reverend",
    "mayor",
    "congresswoman",
    "congressman",
    "lieutenant",
    "chairman",
    "elect"
]

# -------------------------
# Sentence casing
# FIX 1: Added em dash pattern so text after "...word — Next"
# is capitalized when it follows a sentence-ending punctuation mark.
# -------------------------
def sentence_case(text):

    text = text.lower()
    text = text.capitalize()

    # Standard: capitalize after . ! ?
    text = re.sub(
        r"([.!?]\s+)([a-z])",
        lambda m: m.group(1) + m.group(2).upper(),
        text
    )

    # Em dash after sentence-ending punctuation
    # e.g. "We must act.— But only if..." → "We must act.— But only if..."
    text = re.sub(
        r"([.!?]\s*[—–]\s*)([a-z])",
        lambda m: m.group(1) + m.group(2).upper(),
        text
    )

    return text

# -------------------------
# Fix pronouns
# -------------------------
def fix_pronouns(text):

    text = re.sub(r"\bi\b", "I", text)
    text = re.sub(r"\bi'm\b", "I'm", text)
    text = re.sub(r"\bi've\b", "I've", text)
    text = re.sub(r"\bi'll\b", "I'll", text)
    text = re.sub(r"\bi'd\b", "I'd", text)

    return text

# -------------------------
# Middle initials fix
# -------------------------
def fix_middle_initials(text):

    pattern = re.compile(
        r"\b([A-Z][a-z]+)\s+([a-z])\s+([A-Z][a-z]+)\b"
    )

    return pattern.sub(
        lambda m: f"{m.group(1)} {m.group(2).upper()}. {m.group(3)}",
        text
    )

# -------------------------
# Whitelist
# FIX 3: Skip single-character entries — word boundaries
# alone aren't reliable enough for single letters and
# can corrupt ordinary words.
# -------------------------
def apply_whitelist(text):

    targets = sorted(PROPER_NOUNS | ACRONYMS, key=len, reverse=True)

    for word in targets:

        if len(word) == 1:
            continue

        pattern = re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE)

        text = pattern.sub(lambda m: word, text)

    return text

# -------------------------
# spaCy entity correction
# ROOT CAUSE FIX: The original code used str.replace(ent.text, fixed),
# which has no word boundaries. When spaCy tagged "St. Louis" as a GPE
# and produced fixed="St. Louis", the plain replace found every occurrence
# of the substring "st" in the text — corrupting "teamsters" → "teamSters",
# "guests" → "gueSts", "greatest" → "greateSt", etc.
# Fix: use re.sub with \b word boundaries so only the full entity
# token is replaced, never a substring inside another word.
# -------------------------
def spacy_entities(text):

    doc = nlp(text)

    small_words = {"of","the","and","in","on","for","to","at","a","an"}

    for ent in doc.ents:

        if ent.label_ in {"PERSON","ORG","GPE","NORP"}:

            words = ent.text.split()
            fixed_words = []

            for i, w in enumerate(words):

                if i == 0:
                    fixed_words.append(w.capitalize())
                elif w.lower() in small_words:
                    fixed_words.append(w.lower())
                else:
                    fixed_words.append(w.capitalize())

            fixed = " ".join(fixed_words)

            # Word-boundary-safe replacement — never corrupts substrings
            pattern = re.compile(rf"\b{re.escape(ent.text)}\b")
            text = pattern.sub(fixed, text)

    return text

# -------------------------
# Title fixes
# FIX 2: Sort titles longest-first so "vice president"
# matches before "president", and "lieutenant governor"
# matches before "lieutenant". Build the cased title
# dynamically so multi-word titles capitalize correctly.
# -------------------------
def fix_titles(text):

    for title in sorted(TITLES, key=len, reverse=True):

        words = title.split()
        cased_title = " ".join(w.capitalize() for w in words)
        pattern = rf"\b{re.escape(title)}\s+([A-Za-z]+)"

        def repl(m, ct=cased_title):
            return ct + " " + m.group(1).capitalize()

        text = re.sub(pattern, repl, text, flags=re.IGNORECASE)

    return text

# -------------------------
# Speaker correction
# -------------------------
def fix_speaker_name(text, speaker):

    if not isinstance(speaker, str) or not speaker:
        return text

    first = speaker.split()[0]
    pattern = re.compile(rf"\b{first.lower()}\b", re.IGNORECASE)

    return pattern.sub(first, text)

# -------------------------
# Hard post-fixes
# -------------------------
def post_name_fixes(text):

    fixes = {
        r"\bbarack obama\b": "Barack Obama",
        r"\bmichelle obama\b": "Michelle Obama",
        r"\bvice president\b": "Vice President",
        r"\breverend jesse jackson\b": "Reverend Jesse Jackson",
        r"\bida b wells\b": "Ida B. Wells",
    }

    for pattern, replacement in fixes.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    return text

# -------------------------
# Mc / O' fixes
# -------------------------
def fix_name_patterns(text):

    text = re.sub(
        r"\bMc([a-z])",
        lambda m: "Mc" + m.group(1).upper(),
        text
    )

    text = re.sub(
        r"\bO'([a-z])",
        lambda m: "O'" + m.group(1).upper(),
        text
    )

    return text

# -------------------------
# MAIN truecase pipeline
# -------------------------
def truecase_cspan_text(text, speaker):

    if not isinstance(text, str) or not text:
        return text

    text = sentence_case(text)
    text = fix_pronouns(text)
    text = fix_middle_initials(text)
    text = spacy_entities(text)
    text = apply_whitelist(text)
    text = fix_titles(text)
    text = fix_speaker_name(text, speaker)
    text = fix_name_patterns(text)
    text = post_name_fixes(text)

    return text

# -------------------------
# MAIN DRIVER
# -------------------------
def main():

    print("Reading dataset...")

    if not Path(INPUT_FILE).exists():
        print("File not found:", INPUT_FILE)
        return

    df = pd.read_csv(INPUT_FILE)

    col = "speech" if "speech" in df.columns else "text"

    print("Applying truecasing...")

    def process_row(row):

        source = str(row.get("source","")).upper()
        text = str(row[col])
        speaker = str(row.get("speaker",""))

        if "C-SPAN" in source or "CSPAN" in source:
            return truecase_cspan_text(text, speaker)

        return text

    df[col] = df.apply(process_row, axis=1)

    # final word count fix
    df["word_count"] = df[col].astype(str).str.split().apply(len)

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    df.to_csv(OUTPUT_FILE, index=False)

    print("SUCCESS")
    print("Rows processed:", len(df))
    print("Saved to:", OUTPUT_FILE)

if __name__ == "__main__":
    main()