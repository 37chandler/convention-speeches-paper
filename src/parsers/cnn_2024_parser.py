#!/usr/bin/env python3
"""
CNN 2024 Convention Transcript Parser

Reads per-speaker txt files written by src/cnn_parser.py.
Groups base + _seg files by canonical stem, merges text where content differs.

File format written by cnn_parser.py:
    SPEAKER NAME (TITLE OR EMPTY):

    [speech text]

Outputs CSV columns:
    speaker, party, year, night, timestamp, text, word_count, source_file, source
"""

import re
import csv
from pathlib import Path
from dataclasses import dataclass


@dataclass
class Speech:
    speaker: str
    party: str
    year: int
    night: int
    timestamp: str
    text: str
    word_count: int
    source_file: str
    source: str


# ── Constants ─────────────────────────────────────────────────────────────────

RAW_DIR    = Path("data/raw/cnn")
OUTPUT_CSV = Path("data/processed/parsed/parsed_cnn_2024.csv")

FIELDNAMES = [
    "speaker", "party", "year", "night", "timestamp",
    "text", "word_count", "source_file", "source",
]

MIN_WORD_COUNT = 50

NOISE_RE = re.compile(
    r"\((?:CHEERS?\s*(?:AND|&)\s*APPLAUSE|APPLAUSE|AUDIENCE\s*BOOS?|BOOING|"
    r"LAUGHTER|CHANTING|CROWD\s*CHANTING|MUSIC\s*PLAYING|INAUDIBLE|CROSSTALK|"
    r"BEGIN\s*VIDEO\s*CLIP|END\s*VIDEO\s*CLIP|COMMERCIAL\s*BREAK)[^)]*\)",
    re.IGNORECASE,
)

# Speakers CNN clips from the opposing convention — correct their party.
KNOWN_PARTY: dict[str, str] = {
    "Donald Trump":  "Republican",
    "J.D. Vance":    "Republican",
    "Nikki Haley":   "Republican",
    "Joe Biden":     "Democratic",
    "Kamala Harris": "Democratic",
    "Barack Obama":  "Democratic",
}

# Discard any speech whose parsed speaker matches these exactly.
JUNK_SPEAKERS: set[str] = {
    "Chair", "Chairman", "Char", "Ceo", "Vp", "Ok", "Dna",
    "Aliquippa", "Audience", "Speaker", "Announcer", "Narrator",
    "Moderator", "Reporter", "Anchor", "Event Host", "Former Student",
    "Cnn Host And Correspondent", "Cnn Political Commentator",
    "Cnn Senior Political Commentator", "Senior National Correspondent",
    "National Youth Poet Laureate", "Senate Candidate",
    "Vice President Of The United States", "D.C.", "Sidner", "M.J. Lee",
    "Daughter Killed In Uvalde", "Director Of Federal Affairs At Rape",
    "",
}

CNN_ANCHOR_LAST_NAMES: set[str] = {
    "Tapper", "Cooper", "Bash", "Collins", "Phillip", "King", "Blitzer",
    "Burnett", "Hunt", "Berman", "Coates", "Cornish", "Axelrod",
    "Zeleny", "Mattingly", "Gangel", "Lee", "Sidner",
}

EXCLUDE_STEMS: set[str] = {
    "bernie_sanders_cnn_rnc_2024_night_2",  # actually Sarah Huckabee Sanders
    "donald_trump_cnn_dnc_2024_night_3",    # J6 speech, not a 2024 convention speech
    "lara_trump_cnn_rnc_2024_night_3",       # CNN interview segment, not a convention speech
    "maya_harris_cnn_dnc_2024_night_4",      # contains Kamala's acceptance speech — use Rev instead
    "jack_johnson_cnn_rnc_2024_night_1",   # Tennessee delegation roll call - not a speech
    
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def canonical_stem(filename: str) -> str:
    """
    Strip _seg<N> suffix to get the grouping key.

    kamala_harris_cnn_dnc_2024_night_4_seg03  →  kamala_harris_cnn_dnc_2024_night_4
    kamala_harris_cnn_dnc_2024_night_4        →  kamala_harris_cnn_dnc_2024_night_4
    """
    return re.sub(r"_seg\d+$", "", Path(filename).stem)


def parse_party(stem: str) -> str:
    s = stem.lower()
    if "_dnc_" in s:
        return "Democratic"
    if "_rnc_" in s:
        return "Republican"
    return "Unknown"


def parse_night(stem: str) -> int:
    m = re.search(r"night[_\s]?(\d+)", stem, re.IGNORECASE)
    return int(m.group(1)) if m else 0


def parse_header(line: str) -> tuple[str, str]:
    """
    Parse the first line of a CNN txt file.

    'Kamala Harris (Democratic Presidential Candidate):'  →  ('Kamala Harris', 'Democratic Presidential Candidate')
    'Kamala Harris ():'                                   →  ('Kamala Harris', '')
    'Kamala Harris:'                                      →  ('Kamala Harris', '')
    """
    line = line.strip().rstrip(":")
    m = re.match(r"^(.+?)\s*\(([^)]*)\)\s*$", line)
    if m:
        return m.group(1).strip().title(), m.group(2).strip().title()
    return line.strip().title(), ""


def is_junk(speaker: str) -> bool:
    s = speaker.strip().rstrip(".")
    if s in JUNK_SPEAKERS:
        return True
    tokens = s.split()
    # Single-token CNN anchor last names
    if len(tokens) == 1 and tokens[0] in CNN_ANCHOR_LAST_NAMES:
        return True
    # Single-token noise (Ok., Dna., etc.)
    if len(tokens) == 1 and len(s) <= 3:
        return True
    return False


def read_file(path: Path) -> tuple[str, str]:
    """
    Read a CNN txt file.
    Returns (header_line, body_text).
    Header is line 0. Body starts after the first blank line.
    """
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if not lines:
        return "", ""

    header = lines[0]

    body_start = 1
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "":
            body_start = i + 1
            break

    body = "\n".join(lines[body_start:]).strip()
    return header, body


def clean_text(raw: str) -> str:
    text = NOISE_RE.sub("", raw)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


# ── Core ──────────────────────────────────────────────────────────────────────

def group_files(raw_dir: Path) -> dict[str, list[Path]]:
    """
    Group all txt files by canonical stem.

    Returns dict: stem → [base_path, seg_path, ...] sorted base first.
    """
    groups: dict[str, list[Path]] = {}

    for path in sorted(raw_dir.glob("*.txt")):
        key = canonical_stem(path.name)
        groups.setdefault(key, []).append(path)

    # Sort each group: base file first, then segs in filename order
    for key in groups:
        groups[key].sort(
            key=lambda p: (0 if "_seg" not in p.stem else 1, p.stem)
        )

    return groups


def parse_group(stem: str, paths: list[Path]) -> Speech | None:
    """
    Parse a group of files (base + segs) into a single Speech.

    - Speaker name and title always come from the base file (first in list).
    - Text: start with base body, then append any seg body that differs.
    """
    if stem in EXCLUDE_STEMS:
        return None
    
    header_line, base_body = read_file(paths[0])
    if not header_line:
        return None

    speaker, title = parse_header(header_line)

    if is_junk(speaker):
        return None

    # Build merged text
    text_parts = [base_body] if base_body else []

    for seg_path in paths[1:]:
        _, seg_body = read_file(seg_path)
        if seg_body and seg_body.strip() != base_body.strip():
            # Genuinely new content — append it
            text_parts.append(seg_body)

    combined = clean_text("\n\n".join(text_parts))
    word_count = len(combined.split())

    if word_count < MIN_WORD_COUNT:
        return None

    party = parse_party(stem)

    # Fix ghost party — speaker tagged wrong because CNN aired them
    # during the opposing convention's coverage
    if speaker in KNOWN_PARTY:
        party = KNOWN_PARTY[speaker]

    night = parse_night(stem)

    return Speech(
        speaker=speaker,
        party=party,
        year=2024,
        night=night,
        timestamp="",
        text=combined,
        word_count=word_count,
        source_file=paths[0].name,  # always the base file
        source="CNN",
    )



def process_all_cnn_2024(data_dir: Path, output_path: Path) -> list[dict]:
    groups = group_files(data_dir)

    total_files = sum(len(v) for v in groups.values())
    print(f"Found {len(groups)} speaker/night groups from {total_files} files")

    rows = []
    skipped = 0

    for stem, paths in sorted(groups.items()):
        speech = parse_group(stem, paths)

        if speech is None:
            skipped += 1
            continue

        had_segs = len(paths) > 1
        merged   = had_segs and any("_seg" in p.stem for p in paths[1:])
        flag = " [merged]" if merged else ""

        print(f"  {speech.speaker} | {speech.party} | Night {speech.night} | "
              f"{speech.word_count} words{flag}")

        rows.append({f: getattr(speech, f) for f in FIELDNAMES})

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nWrote    {len(rows)} speeches  →  {output_path}")
    print(f"Skipped  {skipped} (junk or too short)")
    return rows


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Parse CNN 2024 convention transcripts")
    ap.add_argument("--data-dir", type=Path, default=RAW_DIR)
    ap.add_argument("--output",   type=Path, default=OUTPUT_CSV)
    args = ap.parse_args()
    process_all_cnn_2024(args.data_dir, args.output)


if __name__ == "__main__":
    main()