#!/usr/bin/env python3
"""
C-SPAN Convention Transcript Parser (2004-2016)

Parses C-SPAN transcripts which have the format:
    HH:MM:SS
    Speaker Name
    SPEECH TEXT IN ALL CAPS...

Outputs a CSV with columns:
    speaker, party, year, night, timestamp, text, word_count, source_file
"""

import re
import csv
from pathlib import Path
from dataclasses import dataclass


@dataclass
class Speech:
    """Represents an extracted speech segment."""
    speaker: str
    party: str
    year: int
    night: int
    timestamp: str
    text: str
    word_count: int
    source_file: str


def parse_cspan_transcript(filepath: Path, year: int, party: str, night: int) -> list[Speech]:
    """
    Parse a single C-SPAN transcript file.

    Args:
        filepath: Path to the transcript file
        year: Election year (2004, 2008, 2012, 2016)
        party: 'Democratic' or 'Republican'
        night: Convention night (1-4)

    Returns:
        List of Speech objects
    """
    content = filepath.read_text(encoding='utf-8', errors='replace')

    # Pattern: timestamp line, then speaker line, then text
    # Timestamp format: HH:MM:SS (at start of line)
    # Speaker is on the next line, may have trailing whitespace/tab
    # Text follows in ALL CAPS until next timestamp

    # Split into segments by timestamp
    timestamp_pattern = re.compile(r'^(\d{2}:\d{2}:\d{2})\s*$', re.MULTILINE)

    # Find all timestamps and their positions
    matches = list(timestamp_pattern.finditer(content))

    speeches = []

    for i, match in enumerate(matches):
        timestamp = match.group(1)
        start_pos = match.end()

        # Get text until next timestamp (or end of file)
        if i + 1 < len(matches):
            end_pos = matches[i + 1].start()
        else:
            end_pos = len(content)

        segment = content[start_pos:end_pos].strip()

        if not segment:
            continue

        # First line is speaker name, rest is speech text
        lines = segment.split('\n', 1)

        if len(lines) < 2:
            continue

        speaker_raw = lines[0].strip()
        text_raw = lines[1].strip() if len(lines) > 1 else ''

        if not speaker_raw or not text_raw:
            continue

        # Clean speaker name
        speaker = clean_speaker_name(speaker_raw)

        # Clean text (normalize whitespace, keep as-is for caps)
        text = clean_text(text_raw)

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
    """Clean and normalize speaker name."""
    # Remove trailing tabs/whitespace
    name = name.strip()

    # Title case (C-SPAN names are often in various cases)
    # But preserve certain patterns like "Jr." or "III"
    name = ' '.join(word.capitalize() if word.lower() not in ('jr', 'jr.', 'sr', 'sr.', 'ii', 'iii', 'iv')
                    else word for word in name.split())

    # Fix common patterns
    name = re.sub(r'\s+', ' ', name)  # Multiple spaces to single

    return name


def clean_text(text: str) -> str:
    """Clean speech text."""
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)

    # Remove stage directions like [APPLAUSE], [CHEERING], etc.
    text = re.sub(r'\[.*?\]', '', text)

    # Remove parenthetical stage directions
    text = re.sub(r'\(APPLAUSE\)', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\(CHEERING\)', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\(BOOING\)', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\(LAUGHTER\)', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\(CROSSTALK\)', '', text, flags=re.IGNORECASE)

    # Clean up extra spaces
    text = re.sub(r'\s+', ' ', text).strip()

    return text


def extract_night_from_filename(filename: str) -> int:
    """Extract night/day number from filename."""
    # Pattern: night-1, night-2, afternoon-1, morning-1, etc.
    # All refer to the convention day
    match = re.search(r'(?:night|afternoon|morning)-(\d+)', filename, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return 0


def process_all_cspan(data_dir: Path, output_path: Path) -> list[dict]:
    """
    Process all C-SPAN transcripts and write to CSV.

    Args:
        data_dir: Path to data/raw/cspan/
        output_path: Path to output CSV file

    Returns:
        List of speech dictionaries
    """
    all_speeches = []

    for year_dir in sorted(data_dir.iterdir()):
        if not year_dir.is_dir():
            continue

        try:
            year = int(year_dir.name)
        except ValueError:
            continue

        if year not in (2004, 2008, 2012, 2016):
            continue

        for party_dir in year_dir.iterdir():
            if not party_dir.is_dir():
                continue

            party = party_dir.name  # 'Democratic' or 'Republican'

            for transcript_file in sorted(party_dir.glob('*.txt')):
                night = extract_night_from_filename(transcript_file.name)

                print(f"Processing: {year} {party} Night {night}")

                speeches = parse_cspan_transcript(
                    transcript_file,
                    year=year,
                    party=party,
                    night=night
                )

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
                        'source': 'CSPAN'
                    })

                print(f"  Extracted {len(speeches)} speeches")

    # Write CSV
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
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Parse C-SPAN convention transcripts (2004-2016)'
    )
    parser.add_argument(
        '--data-dir',
        type=Path,
        default=Path('data/raw/cspan'),
        help='Directory containing C-SPAN transcripts'
    )
    parser.add_argument(
        '--output',
        type=Path,
        default=Path('data/processed/parsed/parsed_cspan_2004_2016.csv'),
        help='Output CSV file'
    )

    args = parser.parse_args()

    speeches = process_all_cspan(args.data_dir, args.output)

    # Summary stats
    if speeches:
        print(f"\n=== Summary ===")
        print(f"Total speeches: {len(speeches)}")

        by_year = {}
        for s in speeches:
            by_year.setdefault(s['year'], []).append(s)

        for year in sorted(by_year.keys()):
            print(f"  {year}: {len(by_year[year])} speeches")


if __name__ == '__main__':
    main()
