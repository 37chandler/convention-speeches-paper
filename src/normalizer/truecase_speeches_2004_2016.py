#!/usr/bin/env python3
"""
truecase_speeches_2004_2016.py

Truecaser for 2004–2016 convention speeches.
Ported from truecase_speeches_2024.py.

Key differences from 2024:
  - All rows are C-SPAN source — no source check needed, every row is processed
  - Column is 'text' (not 'speech')
  - Expanded PROPER_NOUNS and ACRONYMS to cover 2004–2016 speakers and era terms

Patches applied after audit:
  1. fix_pronouns: negative lookbehind on [A-Z]\. prevents H.I.V./G.I. false positives
  2. post_name_fixes: u.s. → U.S. (dotted form not caught by ACRONYMS word-boundary match)
  3. post_name_fixes: all months added (January–December; May only when followed by a digit)
  4. post_name_fixes: spaCy overcapitalization fixed — "President Of The" → "President of the"
     and Espaillat added as hard name fix
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
INPUT_FILE  = "data/processed/normalized/normalized_speeches_2004_2016.csv"
OUTPUT_FILE = "data/processed/normalized/truecased_speeches_2004_2016.csv"

# -------------------------
# ACRONYMS
# -------------------------
ACRONYMS = {
    "USA", "DNC", "RNC", "GOP", "FBI", "CIA", "NATO", "UN", "EU",
    "MAGA", "IVF", "COVID", "LGBTQ", "VP", "POTUS", "CEO",
    "AOC", "MLK", "JFK", "DNA", "TV", "II", "III", "IV",
    # Era-specific
    "WMD", "FEMA", "TARP", "ACA", "AIG", "GM", "UAW",
    "LGBT", "HIV", "AIDS", "STEM", "NSA", "TSA", "ICE",
}

# -------------------------
# PROPER NOUNS
# Expanded for 2004–2016 speakers and political figures.
# Single-letter entries intentionally excluded (corrupts substrings).
# -------------------------
PROPER_NOUNS = {
    # Core 2024 carry-overs
    "Barack", "Donald", "Joe", "Kamala", "Tim",
    "Biden", "Trump", "Harris", "Walz", "Vance",
    "Chicago", "Milwaukee", "Mississippi", "Delaware", "California",
    "Native", "American", "Democrat", "Democratic", "Republican",
    "Congress", "Senate", "White House", "God", "Jesus",

    # 2004–2016 presidential/VP tickets
    "Kerry", "Edwards", "McCain", "Palin", "Romney", "Ryan",
    "Obama", "Clinton", "Bush", "Gore", "Cheney",
    "Hillary", "Michelle", "Laura", "Jill", "Cindy", "Ann",
    "Mitt", "Sarah", "Paul", "John", "George",

    # Prominent speakers — last names
    "Abrams", "Albright", "Allen", "Angelou", "Ayotte",
    "Bachmann", "Baio", "Baldwin", "Barbour", "Barney", "Bass",
    "Bassett", "Bayh", "Becerra", "Biden", "Bingaman",
    "Blackburn", "Bloomberg", "Boehner", "Bond", "Bondi",
    "Booker", "Boxer", "Brazile", "Brownback", "Burr",
    "Campbell", "Cantwell", "Capito", "Carnahan", "Carson",
    "Carter", "Casey", "Castro", "Chafee", "Chao",
    "Christie", "Clyburn", "Coleman", "Collins", "Condoleezza",
    "Coors", "Cotton", "Crist", "Cruz", "Cuomo",
    "Daines", "Daschle", "Davis", "Dean", "DeLauro",
    "DeMint", "DeGette", "Demings", "Dole", "Dorgan",
    "Duckworth", "Duffy", "Duncan", "Durbin",
    "Eisenhower", "Ellison", "Emanuel", "Ensign", "Ernst",
    "Fallin", "Fattah", "Fiorina", "Fischer", "Flanagan",
    "Fluke", "Flynn", "Ford", "Frank", "Franken", "Franks",
    "Frist", "Fulton",
    "Gabbard", "Giffords", "Gillibrand", "Gillum", "Gingrich",
    "Giuliani", "Glenn", "Gonzalez", "Gore", "Graham",
    "Granholm", "Grijalva", "Gutierrez",
    "Hagan", "Haley", "Hamm", "Harkin", "Harris", "Harvey",
    "Heinz", "Hickenlooper", "Hirono", "Hoeven", "Hoffa",
    "Holder", "Hoyer", "Huckabee", "Huerta", "Huntsman",
    "Hutchinson", "Ingraham", "Ivanka",
    "Jackson", "Jacques", "Jealous", "Jeffries",
    "Jesse", "Jill", "Jimmy", "Joaquin", "Johnson", "Julian",
    "Kaine", "Kasich", "Kathleen", "Kennedy", "Kerik",
    "King", "Kirsten", "Klobuchar", "Kucinich",
    "Landrieu", "Lautenberg", "Leahy", "Ledbetter", "Levin",
    "Lewis", "Lincoln", "Lingle", "Locke", "Longoria", "Lovato",
    "Lowey", "Lujan", "Luther", "Luttrell",
    "Madeleine", "Madigan", "Malloy", "Maloney", "Manchin",
    "Marcus", "Markey", "Marsha", "Martinez", "Maxine",
    "McAuliffe", "McCain", "McCarthy", "McCaskill", "McConnell",
    "McCrory", "McMorris", "Mel", "Melania", "Menendez",
    "Merkley", "Messina", "Mia", "Michele", "Michelle",
    "Mikulski", "Mitch", "Mitt", "Moore", "Murphy", "Murray",
    "Napolitano", "Nethercutt", "Newsom", "Newt", "Nikki",
    "Norton", "Obama", "Palin", "Panetta", "Patricia",
    "Pawlenty", "Peggy", "Pelosi", "Pence", "Perdue",
    "Perkins", "Perry", "Pierluisi", "Podesta", "Polis",
    "Portman", "Priebus",
    "Rahm", "Rand", "Rangel", "Raul", "Reagan", "Reed",
    "Reid", "Reince", "Rendell", "Rice", "Richards",
    "Richardson", "Richmond", "Ridge", "Romney", "Rosa",
    "Rudy", "Ryan",
    "Salazar", "Sanders", "Sandoval", "Santorum", "Schiff",
    "Schumer", "Schwarzenegger", "Schweitzer", "Scott",
    "Sebelius", "Sessions", "Shaheen", "Sharpton", "Sheila",
    "Shinseki", "Shirley", "Silverman", "Simone", "Slaughter",
    "Solis", "Sorensen", "Stabenow", "Stacey", "Steele",
    "Stephanie", "Strickland", "Sullivan", "Susana", "Sybrina",
    "Tammy", "Teresa", "Theodore", "Thompson", "Tiffany",
    "Trumka", "Tulsi",
    "Val", "Vanessa", "Villaraigosa", "Vilsack",
    "Walker", "Warner", "Warren", "Waters", "Watson",
    "Watt", "Weaver", "Weingarten", "Wesley", "Wilson",
    "Xavier", "Zell", "Zinke",

    # Places common in convention speeches
    "Iraq", "Afghanistan", "Iran", "Israel", "Palestine",
    "America", "Americans", "African", "Latino", "Latina",
    "Hispanic", "Asian", "Medicare", "Medicaid", "Obamacare",
    "Wall Street", "Main Street",
}

# -------------------------
# TITLES (identical to 2024)
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
    "elect",
    "secretary",          # added — era has many "Secretary of State/Defense"
    "ambassador",         # added — common in foreign policy speeches
]

# -------------------------
# Sentence casing (identical to 2024)
# -------------------------
def sentence_case(text):
    text = text.lower()
    text = text.capitalize()
    text = re.sub(
        r"([.!?]\s+)([a-z])",
        lambda m: m.group(1) + m.group(2).upper(),
        text
    )
    text = re.sub(
        r"([.!?]\s*[—–]\s*)([a-z])",
        lambda m: m.group(1) + m.group(2).upper(),
        text
    )
    return text

# -------------------------
# Fix pronouns
# Negative lookbehind on [A-Z]\. prevents matching the dotted
# letter in abbreviations like H.I.V. and G.I. Bill.
# -------------------------
def fix_pronouns(text):
    text = re.sub(r"(?<![A-Z]\.)\bi\b", "I", text)
    text = re.sub(r"\bi'm\b", "I'm", text)
    text = re.sub(r"\bi've\b", "I've", text)
    text = re.sub(r"\bi'll\b", "I'll", text)
    text = re.sub(r"\bi'd\b", "I'd", text)
    return text

# -------------------------
# Middle initials fix (identical to 2024)
# -------------------------
def fix_middle_initials(text):
    pattern = re.compile(r"\b([A-Z][a-z]+)\s+([a-z])\s+([A-Z][a-z]+)\b")
    return pattern.sub(
        lambda m: f"{m.group(1)} {m.group(2).upper()}. {m.group(3)}",
        text
    )

# -------------------------
# Whitelist (identical to 2024 — single-char entries skipped)
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
# spaCy entity correction (identical to 2024 — word-boundary-safe)
# -------------------------
def spacy_entities(text):
    doc = nlp(text)
    small_words = {"of", "the", "and", "in", "on", "for", "to", "at", "a", "an"}
    for ent in doc.ents:
        if ent.label_ in {"PERSON", "ORG", "GPE", "NORP"}:
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
            pattern = re.compile(rf"\b{re.escape(ent.text)}\b")
            text = pattern.sub(fixed, text)
    return text

# -------------------------
# Title fixes (identical to 2024)
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
# Speaker correction (identical to 2024)
# -------------------------
def fix_speaker_name(text, speaker):
    if not isinstance(speaker, str) or not speaker:
        return text
    first = speaker.split()[0]
    pattern = re.compile(rf"\b{first.lower()}\b", re.IGNORECASE)
    return pattern.sub(first, text)

# -------------------------
# Hard post-fixes (expanded for 2004–2016 era)
# -------------------------
def post_name_fixes(text):
    fixes = {
        # Major names
        r"\bbarack obama\b":           "Barack Obama",
        r"\bmichelle obama\b":         "Michelle Obama",
        r"\bjohn kerry\b":             "John Kerry",
        r"\bjohn edwards\b":           "John Edwards",
        r"\bjohn mccain\b":            "John McCain",
        r"\bsarah palin\b":            "Sarah Palin",
        r"\bmitt romney\b":            "Mitt Romney",
        r"\bpaul ryan\b":              "Paul Ryan",
        r"\bhillary clinton\b":        "Hillary Clinton",
        r"\bbill clinton\b":           "Bill Clinton",
        r"\bgeorge w\. bush\b":        "George W. Bush",
        r"\bgeorge bush\b":            "George Bush",
        r"\bcondoleezza rice\b":       "Condoleezza Rice",
        r"\bdick cheney\b":            "Dick Cheney",
        r"\bal gore\b":                "Al Gore",
        r"\badriano espaillat\b":      "Adriano Espaillat",
        # Titles
        r"\bvice president\b":         "Vice President",
        r"\breverend jesse jackson\b": "Reverend Jesse Jackson",
        r"\bida b wells\b":            "Ida B. Wells",
        r"\bmartin luther king\b":     "Martin Luther King",
        # Fix spaCy overcapitalization of title+preposition combos
        r"\bPresident Of The\b":       "President of the",
        r"\bPresident Of These\b":     "President of these",
        r"\bOf The United States\b":   "of the United States",
        r"\bOf These United States\b": "of these United States",
        r"\bCongressman In\b":         "Congressman in",
        r"\bSenator In\b":             "Senator in",
        r"\bIn The\b":                 "in the",
        r"\bAt The\b":                 "at the",
        r"\bFor The\b":                "for the",
        # Places / phrases
        r"\bwall street\b":            "Wall Street",
        r"\bmain street\b":            "Main Street",
        # Fix u.s. → U.S.
        r"\bu\.s\.\b":                 "U.S.",
        r"\bu\.s\b":                   "U.S.",
        # Months
        r"\bjanuary\b":   "January",
        r"\bmay\b(?=\s+\d)": "May",   # only capitalize 'may' when followed by a date number
        r"\bfebruary\b":  "February",
        r"\bmarch\b":     "March",
        r"\bapril\b":     "April",
        r"\bjune\b":      "June",
        r"\bjuly\b":      "July",
        r"\baugust\b":    "August",
        r"\bseptember\b": "September",
        r"\boctober\b":   "October",
        r"\bnovember\b":  "November",
        r"\bdecember\b":  "December",
    }
    for pattern, replacement in fixes.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text

# -------------------------
# Mc / O' fixes (identical to 2024)
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
# MAIN truecase pipeline (identical to 2024)
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
# All rows are C-SPAN — no source check needed.
# -------------------------
def main():
    print("Reading dataset...")

    if not Path(INPUT_FILE).exists():
        print("File not found:", INPUT_FILE)
        return

    df = pd.read_csv(INPUT_FILE)

    # Column is 'text' in 2004–2016 (not 'speech')
    col = "text" if "text" in df.columns else "speech"

    print(f"Processing {len(df)} rows (column: '{col}')...")

    df[col] = df.apply(
        lambda row: truecase_cspan_text(str(row[col]), str(row.get("speaker", ""))),
        axis=1
    )

    # Recompute word count
    df["word_count"] = df[col].astype(str).str.split().apply(len)

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    df.to_csv(OUTPUT_FILE, index=False)

    print("SUCCESS")
    print("Rows processed:", len(df))
    print("Saved to:", OUTPUT_FILE)

if __name__ == "__main__":
    main()