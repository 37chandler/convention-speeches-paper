#!/usr/bin/env python3
"""
Rev.com 2020 Convention Transcript Parser

Parses Rev.com transcripts which have the format:
    Speaker Name: ( HH:MM:SS ) Text continues here...

The files contain website header cruft that needs to be stripped.

Outputs a CSV with columns:
    speaker, party, year, night, timestamp, text, word_count, source_file
"""

import re
import csv
from pathlib import Path
from dataclasses import dataclass


# Known speaker name fixes from original analysis
SPEAKER_FIXES = {
    'Will we see to it that no one who works full time can live in poverty Pete Buttigieg': 'Pete Buttigieg',
    'I stayed for an hour and a half- Jamie Ponder': 'Jamie Ponder',
    'It seems like just yesterday that we were at our first convention- Melania Trump': 'Melania Trump',
    'The night before I fought back- Kayleigh McEnany': 'Kayleigh McEnany',
    'It is a sad irony that Jackie immigrated- Speaker 8': 'Speaker 8',
    'I withdrew from the terrible one- Donald Trump': 'Donald Trump',
    'Alaska casts seven votes for Bernie- Chuck Degnan': 'Chuck Degnan',
    'A lot of us were shocked and I think what gives me hope- Art Acevedo': 'Art Acevedo',
    'But Joe Biden is a guy who has earned the respect- Eva Longoria': 'Eva Longoria',
    'And the promise of our country led by president Joe Biden and vice-president Kamala Harris Kerry Washington': 'Kerry Washington',
    'Joe will also- Senator Bernie Sanders': 'Senator Bernie Sanders',
}

# Boundary pattern that ignores periods in common abbreviations
BOUNDARY_PATTERN = re.compile(r'(?<!Jr)(?<!Sr)(?<!Dr)(?<!Mr)(?<!Mrs)(?<!St)(?<![A-Z])[.!?\n]\s*')



# Rev.com website footer markers
FOOTER_MARKERS = [
    'Other Related Transcripts',
    'Stay updated. Get a weekly digest',
    'Transcription Overview',
    '© Rev.com',
    'support@rev.com',
    '222 Kearny St',
    'Posted by NPR',
]


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


def strip_header(content: str) -> str:
    speaker_pattern = re.compile(r'^[A-Za-z][^:]+:\s*\(\s*\d{1,2}:\d{2}(?::\d{2})?\s*\)', re.MULTILINE)
    match = speaker_pattern.search(content)
    if match:
        return content[match.start():]
    return content


def parse_rev_2020_transcript(filepath: Path, year: int, party: str, night: int) -> list[Speech]:
    content = filepath.read_text(encoding='utf-8', errors='replace')
    content = strip_header(content)

    timestamp_pattern = re.compile(r':\s*\(\s*(\d{1,2}:\d{2}(?::\d{2})?)\s*\)')
    matches = list(timestamp_pattern.finditer(content))
    speeches = []

    for i, match in enumerate(matches):
        timestamp = match.group(1).strip()
        colon_pos = match.start()
        search_start = max(0, colon_pos - 60)
        prefix = content[search_start:colon_pos]
        boundary_matches = list(BOUNDARY_PATTERN.finditer(prefix))

        if boundary_matches:
            last_boundary = boundary_matches[-1]
            speaker_start = search_start + last_boundary.end()
        else:
            speaker_start = search_start

        speaker_raw = content[speaker_start:colon_pos].strip()

        start_pos = match.end()
        if i + 1 < len(matches):
            next_match = matches[i + 1]
            next_colon_pos = next_match.start()
            next_search_start = max(0, next_colon_pos - 60)
            next_prefix = content[next_search_start:next_colon_pos]
            next_boundary_matches = list(BOUNDARY_PATTERN.finditer(next_prefix))
            if next_boundary_matches:
                end_pos = next_search_start + next_boundary_matches[-1].end()
            else:
                end_pos = next_search_start
        else:
            end_pos = len(content)

        text = content[start_pos:end_pos].strip()

        if not text:
            continue

        speaker = clean_speaker_name(speaker_raw)

        if not is_valid_speaker_name(speaker):
            continue

        text = clean_text(text)

        if not text:
            continue

        word_count = len(text.split())

        speeches.append(Speech(
            speaker=speaker,
            party=party,
            year=year,
            night=night,
            timestamp=timestamp,
            text=text,
            word_count=word_count,
            source_file=filepath.name
        ))

    return speeches


def clean_speaker_name(name: str) -> str:
    if name in SPEAKER_FIXES:
        name = SPEAKER_FIXES[name]
    # Remove title prefixes like Dr., Mr., Mrs., Ms., Rev.
    name = re.sub(r'^(Dr|Mr|Mrs|Ms|Rev)\.\s*', '', name).strip()
    name = re.sub(r'\s+', ' ', name).strip()
    name = name.rstrip(',;:')
    return name


def is_valid_speaker_name(name: str) -> bool:
    if not name or len(name) < 2:
        return False

    # Allow names with single initial surname like "Eugene F." or "Lisa P."
    if re.match(r'^[A-Z][a-z]+ [A-Z]\.$', name):
        return True

    words = name.split()
    if len(words) > 6:
        return False

    if re.search(r'\.\s+[A-Z]', name):
        return False

    name_lower = name.lower()
    fragment_patterns = [
        r'\band\b', r'\bbut\b', r'\bso\b', r'\bor\b',
        r'\bthe\b', r'\ban\b',
        r'\bamerica\b', r'\bamen\b', r'\babsolutely\b',
        r'\bthank you\b', r'\byes\b', r'\bno\b', r'\bwell\b',
        r'\bok\b', r'\bokay\b', r'\bright\b', r'\bnow\b',
        r'\ball of\b', r'\bis\b', r'\bare\b', r'\bwas\b',
        r'\bwere\b', r'\bwill\b', r'\bcan\b',
        r'\bto\b', r'\bfor\b', r'\bwith\b', r'\bfrom\b',
        r'\bthat\b', r'\bthis\b', r'\bappreciate\b',
        r'\bgreat\b', r'\bgood\b', r'\bbye\b', r'\bhello\b',
    ]
    for pattern in fragment_patterns:
        if re.search(pattern, name_lower):
            return False

    if name_lower.startswith('a '):
        return False

    if len(name) == 1:
        return False

    if not name[0].isupper():
        return False

    return True


def clean_text(text: str) -> str:
    text = re.sub(r'\s+', ' ', text)

    # Remove Rev.com website footer noise
    for marker in FOOTER_MARKERS:
        pos = text.find(marker)
        if pos != -1:
            text = text[:pos].strip()

    # Remove all bracketed annotations
    text = re.sub(r'\[.*?\]\.?', '', text, flags=re.IGNORECASE)

    # Remove parenthetical notes
    text = re.sub(r'\(singing\)', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\(applause\)', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\(cheering\)', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\(music\)', '', text, flags=re.IGNORECASE)

    text = re.sub(r'\s+', ' ', text).strip()
    return text


def extract_night_from_filename(filename: str) -> int:
    match = re.search(r'night-?(\d+)', filename, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return 0


def process_all_rev_2020(data_dir: Path, output_path: Path) -> list[dict]:
    all_speeches = []

    for party_dir in sorted(data_dir.iterdir()):
        if not party_dir.is_dir():
            continue

        party = party_dir.name

        for transcript_file in sorted(party_dir.glob('*.txt')):
            night = extract_night_from_filename(transcript_file.name)
            print(f"Processing: 2020 {party} Night {night}")
            speeches = parse_rev_2020_transcript(transcript_file, year=2020, party=party, night=night)

            for speech in speeches:
                all_speeches.append({
                    'speaker': speech.speaker,
                    'party': speech.party,
                    'year': speech.year,
                    'night': speech.night,
                    'timestamp': speech.timestamp,
                    'text': speech.text,
                    'word_count': speech.word_count,
                    'source_file': speech.source_file,
                    'source': 'REV'
                })

            print(f"  Extracted {len(speeches)} speeches")

    if all_speeches:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = ['speaker', 'party', 'year', 'night', 'timestamp',
                      'text', 'word_count', 'source_file', 'source']
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_speeches)
        print(f"\nWrote {len(all_speeches)} speeches to {output_path}")

    return all_speeches


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Parse Rev.com 2020 convention transcripts')
    parser.add_argument('--data-dir', type=Path, default=Path('data/raw/rev/2020'))
    parser.add_argument('--output', type=Path, default=Path('data/processed/parsed/parsed_rev_2020.csv'))
    args = parser.parse_args()
    speeches = process_all_rev_2020(args.data_dir, args.output)
    if speeches:
        print(f"\n=== Summary ===")
        print(f"Total speeches: {len(speeches)}")
        by_party = {}
        for s in speeches:
            by_party.setdefault(s['party'], []).append(s)
        for party in sorted(by_party.keys()):
            print(f"  {party}: {len(by_party[party])} speeches")


if __name__ == '__main__':
    main()