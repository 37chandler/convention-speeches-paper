#!/usr/bin/env python3
"""
CNN Convention Transcript Parser

Fetches CNN convention transcripts and extracts individual speeches,
filtering out CNN commentators and saving each speaker to a separate file.
"""

import re
import os
import time
import requests
from pathlib import Path
from bs4 import BeautifulSoup
from dataclasses import dataclass
from typing import Optional
import csv

# CNN commentators and anchors to filter out (both full names and last names)
CNN_PERSONNEL = {
    # Anchors and hosts - full names
    'jake tapper', 'anderson cooper', 'dana bash', 'kaitlan collins',
    'abby phillip', 'john king', 'wolf blitzer', 'erin burnett',
    'kasie hunt', 'john berman', 'laura coates', 'audie cornish',
    # Last names only (CNN uses these in transcript)
    'tapper', 'cooper', 'bash', 'collins', 'phillip', 'king', 'blitzer',
    'burnett', 'hunt', 'berman', 'coates', 'cornish',
    # Commentators and analysts - full names
    'van jones', 'david axelrod', 'scott jennings', 'alyssa farah griffin',
    'kate bedingfield', 'jonah goldberg', 'chris wallace', 'david urban',
    'ashley allison', 'jamal simmons', 'se cupp', 'bakari sellers',
    'gloria borger', 'jeff zeleny', 'jamie gangel', 'nia-malika henderson',
    'kristen holmes', 'mj lee', 'priscilla alvarez', 'phil mattingly',
    'kayla tausche', 'eva mckend', 'omar jimenez', 'shimon prokupecz',
    # Last names
    'jones', 'axelrod', 'jennings', 'bedingfield', 'goldberg', 'wallace',
    'urban', 'allison', 'simmons', 'cupp', 'sellers', 'borger', 'zeleny',
    'gangel', 'henderson', 'holmes', 'lee', 'alvarez', 'mattingly',
    'tausche', 'mckend', 'jimenez', 'prokupecz',
    # Generic labels and non-speakers
    'announcer', 'unidentified male', 'unidentified female', 'crowd',
    'protesters', 'reporter', 'anchor', 'host', 'commentator',
    'voice-over', 'voiceover', 'narrator', 'moderator',
    # State names (appear in roll call)
    'alabama', 'alaska', 'arizona', 'arkansas', 'california', 'colorado',
    'connecticut', 'delaware', 'florida', 'georgia', 'hawaii', 'idaho',
    'illinois', 'indiana', 'iowa', 'kansas', 'kentucky', 'louisiana',
    'maine', 'maryland', 'massachusetts', 'michigan', 'minnesota',
    'mississippi', 'missouri', 'montana', 'nebraska', 'nevada',
    'new hampshire', 'new jersey', 'new mexico', 'new york',
    'north carolina', 'north dakota', 'ohio', 'oklahoma', 'oregon',
    'pennsylvania', 'rhode island', 'south carolina', 'south dakota',
    'tennessee', 'texas', 'utah', 'vermont', 'virginia', 'washington',
    'west virginia', 'wisconsin', 'wyoming', 'district of columbia',
    'puerto rico', 'guam', 'virgin islands', 'american samoa',
}

# Known convention speakers - maps last name to full name for speakers
# who may only appear as last-name labels in CNN transcripts
KNOWN_SPEAKERS_BY_LAST_NAME = {
    # DNC speakers
    'harris': 'Kamala Harris',
    'walz': 'Tim Walz',
    'biden': 'Joe Biden',  # Also Jill, Ashley - may need context
    'obama': 'Barack Obama',  # Also Michelle - may need context
    'clinton': 'Bill Clinton',  # Also Hillary
    'pelosi': 'Nancy Pelosi',
    'jeffries': 'Hakeem Jeffries',
    'schumer': 'Chuck Schumer',
    'sanders': 'Bernie Sanders',
    'ocasio-cortez': 'Alexandria Ocasio-Cortez',
    'buttigieg': 'Pete Buttigieg',
    'winfrey': 'Oprah Winfrey',
    'shapiro': 'Josh Shapiro',
    'moore': 'Wes Moore',
    'whitmer': 'Gretchen Whitmer',
    'cooper': 'Roy Cooper',
    'klobuchar': 'Amy Klobuchar',
    'warnock': 'Raphael Warnock',
    'booker': 'Cory Booker',
    'emhoff': 'Doug Emhoff',
    'kinzinger': 'Adam Kinzinger',
    'giffords': 'Gabrielle Giffords',
    'kelly': 'Mark Kelly',
    'pritzker': 'J.B. Pritzker',
    'duckworth': 'Tammy Duckworth',
    'beshear': 'Andy Beshear',
    'raskin': 'Jamie Raskin',
    'clyburn': 'James Clyburn',
    'crockett': 'Jasmine Crockett',
    'gorman': 'Amanda Gorman',
    'masto': 'Catherine Cortez Masto',
    'murphy': 'Chris Murphy',
    'panetta': 'Leon Panetta',
    'haaland': 'Deb Haaland',
    'healey': 'Maura Healey',
    'gallego': 'Ruben Gallego',
    'mcbath': 'Lucy McBath',
    'padilla': 'Alex Padilla',
    'warren': 'Elizabeth Warren',
    'durbin': 'Dick Durbin',
    'fain': 'Shawn Fain',
    # RNC speakers
    'trump': 'Donald Trump',  # Also family members
    'vance': 'J.D. Vance',
    'haley': 'Nikki Haley',
    'desantis': 'Ron DeSantis',
    'rubio': 'Marco Rubio',
    'cruz': 'Ted Cruz',
    'scott': 'Tim Scott',  # Also Rick Scott
    'johnson': 'Mike Johnson',
    'scalise': 'Steve Scalise',
    'stefanik': 'Elise Stefanik',
    'greene': 'Marjorie Taylor Greene',
    'gaetz': 'Matt Gaetz',
    'ramaswamy': 'Vivek Ramaswamy',
    'carlson': 'Tucker Carlson',
    'hogan': 'Hulk Hogan',
    'white': 'Dana White',
    'carson': 'Ben Carson',
    'noem': 'Kristi Noem',
    'youngkin': 'Glenn Youngkin',
    'burgum': 'Doug Burgum',
    'abbott': 'Greg Abbott',
    'gingrich': 'Newt Gingrich',
    'guilfoyle': 'Kimberly Guilfoyle',
    'conway': 'Kellyanne Conway',
    'pompeo': 'Mike Pompeo',
    'mcmahon': 'Linda McMahon',
    'graham': 'Franklin Graham',
    'lake': 'Kari Lake',
    'britt': 'Katie Britt',
    'cotton': 'Tom Cotton',
    'mace': 'Nancy Mace',
    'blackburn': 'Marsha Blackburn',
}


@dataclass
class Speech:
    """Represents an extracted speech from the transcript."""
    speaker: str
    title: str
    text: str
    party: str
    night: int
    segment: int
    date: str
    word_count: int

    def filename(self) -> str:
        """Generate a filename for this speech."""
        # Normalize speaker name for filename
        name = self.speaker.lower()
        name = re.sub(r'[^\w\s]', '', name)
        name = re.sub(r'\s+', '_', name.strip())

        convention = 'dnc' if self.party == 'Democratic' else 'rnc'
        return f"{name}_cnn_{convention}_2024_night_{self.night}.txt"


def fetch_transcript(date: str, segment: int) -> Optional[str]:
    """
    Fetch a CNN transcript for a given date and segment.

    Args:
        date: Date in YYYY-MM-DD format
        segment: Segment number (01, 02, etc.)

    Returns:
        Raw HTML content or None if not found
    """
    url = f"https://transcripts.cnn.com/show/se/date/{date}/segment/{segment:02d}"

    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)

        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.text

    except requests.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return None


def parse_transcript(html: str) -> list[tuple[str, str, str, bool]]:
    """
    Parse CNN transcript HTML into speaker segments.

    Returns:
        List of (speaker_name, title, speech_text, is_in_video_clip) tuples
    """
    soup = BeautifulSoup(html, 'html.parser')

    # Find the transcript body - CNN uses specific classes
    # The transcript is typically in a div with class containing 'transcript'
    body = soup.find('div', class_=re.compile(r'cnnTransStoryBody|cnnBodyText|transcript'))

    if not body:
        # Try to find by looking for the text pattern
        body = soup.find('body') or soup

    text = body.get_text(separator='\n')

    # Remove video clip content - these are replays, not live speeches
    # Track positions of video clips
    video_clip_ranges = []
    for match in re.finditer(r'\(BEGIN VIDEO CLIP\)(.*?)\(END VIDEO CLIP\)', text, re.DOTALL):
        video_clip_ranges.append((match.start(), match.end()))

    # Pattern to match speaker labels in CNN transcripts
    # Format: SPEAKER NAME, TITLE: or SPEAKER NAME:
    # Sometimes preceded by timestamp [HH:MM:SS]
    speaker_pattern = re.compile(
        r'(?:\[[\d:]+\]\s*)?'  # Optional timestamp
        r'([A-Z][A-Z\s\.\-\']+(?:,\s*[A-Z][A-Za-z\s\.\-\(\)]+)?)\s*:\s*',
        re.MULTILINE
    )

    def is_in_video_clip(pos: int) -> bool:
        """Check if a position is inside a video clip."""
        for start, end in video_clip_ranges:
            if start <= pos <= end:
                return True
        return False

    segments = []
    matches = list(speaker_pattern.finditer(text))

    for i, match in enumerate(matches):
        speaker_full = match.group(1).strip()

        # Check if this segment is inside a video clip
        in_clip = is_in_video_clip(match.start())

        # Split speaker name and title
        if ',' in speaker_full:
            parts = speaker_full.split(',', 1)
            speaker = parts[0].strip()
            title = parts[1].strip() if len(parts) > 1 else ''
        else:
            speaker = speaker_full
            title = ''

        # Get text until next speaker
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        speech_text = text[start:end].strip()

        # Clean up the text
        speech_text = re.sub(r'\[[\d:]+\]', '', speech_text)  # Remove timestamps
        speech_text = re.sub(r'\(APPLAUSE\)', '', speech_text)
        speech_text = re.sub(r'\(CHEERING\)', '', speech_text)
        speech_text = re.sub(r'\(BOOING\)', '', speech_text)
        speech_text = re.sub(r'\(LAUGHTER\)', '', speech_text)
        speech_text = re.sub(r'\(CROSSTALK\)', '', speech_text)
        speech_text = re.sub(r'\(MUSIC\)', '', speech_text)
        speech_text = re.sub(r'\(BEGIN VIDEO CLIP\)', '', speech_text)
        speech_text = re.sub(r'\(END VIDEO CLIP\)', '', speech_text)
        speech_text = re.sub(r'\(COMMERCIAL BREAK\)', '', speech_text)
        speech_text = re.sub(r'\s+', ' ', speech_text).strip()

        if speech_text:
            segments.append((speaker, title, speech_text, in_clip))

    return segments


def is_cnn_personnel(speaker: str, title: str = '') -> bool:
    """Check if a speaker is CNN personnel (should be filtered)."""
    speaker_lower = speaker.lower().strip()
    title_lower = title.lower() if title else ''

    # If title explicitly mentions CNN, it's CNN personnel
    if 'cnn' in title_lower:
        return True

    # If title mentions a political role, NOT CNN personnel
    political_titles = ['senator', 'governor', 'representative', 'president',
                       'secretary', 'mayor', 'attorney general', 'congressman',
                       'congresswoman', 'delegate', 'candidate']
    if any(pt in title_lower for pt in political_titles):
        return False

    # Direct match on full speaker name
    if speaker_lower in CNN_PERSONNEL:
        return True

    # For last-name-only matches, be more careful
    # Only filter if it's clearly a CNN anchor/correspondent last name
    cnn_anchor_last_names = {
        'tapper', 'cooper', 'bash', 'collins', 'phillip', 'king', 'blitzer',
        'burnett', 'hunt', 'berman', 'coates', 'cornish', 'axelrod', 'jennings',
        'jones', 'zeleny', 'mattingly', 'gangel', 'griffin',
    }

    # Also filter out noise patterns
    noise_patterns = ['dna', 'ok', 'et', 'crowd']
    if speaker_lower.strip().rstrip('.') in noise_patterns:
        return True

    words = speaker_lower.split()
    if len(words) == 1 and words[0] in cnn_anchor_last_names:
        return True

    # Full name matches (more permissive)
    cnn_full_names = [
        'jake tapper', 'anderson cooper', 'dana bash', 'kaitlan collins',
        'abby phillip', 'john king', 'wolf blitzer', 'erin burnett',
        'kasie hunt', 'john berman', 'laura coates', 'audie cornish',
        'van jones', 'david axelrod', 'scott jennings', 'alyssa farah griffin',
        'kate bedingfield', 'jonah goldberg', 'chris wallace', 'david urban',
    ]
    for name in cnn_full_names:
        if name in speaker_lower:
            return True

    return False


def normalize_speaker_key(speaker: str, known_full_names: dict) -> tuple[str, str]:
    """
    Normalize a speaker name, merging last-name-only labels with full names.

    Args:
        speaker: The speaker label from the transcript
        known_full_names: Dict mapping last names to (full_key, display_name, title)

    Returns:
        (normalized_key, display_name) tuple
    """
    speaker_clean = speaker.strip()
    speaker_lower = speaker_clean.lower()

    # Check if this is a last-name-only label
    words = speaker_lower.split()
    if len(words) == 1:
        last_name = words[0]
        # First try transcript-derived full names
        if last_name in known_full_names:
            full_key, display_name, _ = known_full_names[last_name]
            return full_key, display_name
        # Fall back to our known speakers list
        if last_name in KNOWN_SPEAKERS_BY_LAST_NAME:
            full_name = KNOWN_SPEAKERS_BY_LAST_NAME[last_name]
            return full_name.lower(), full_name

    # Handle cases like "K. HARRIS" or "M. HARRIS"
    if '.' in speaker_clean and len(words) >= 2:
        last_name = extract_last_name(speaker)
        if last_name in known_full_names:
            full_key, display_name, _ = known_full_names[last_name]
            return full_key, display_name
        if last_name in KNOWN_SPEAKERS_BY_LAST_NAME:
            full_name = KNOWN_SPEAKERS_BY_LAST_NAME[last_name]
            return full_name.lower(), full_name

    return speaker_lower, speaker_clean


def extract_last_name(speaker: str) -> str:
    """Extract the last name from a speaker label like 'GOV. JOSH SHAPIRO'."""
    # Remove common prefixes
    speaker_clean = speaker.upper().strip()
    for prefix in ['GOV.', 'REP.', 'SEN.', 'DR.', 'REV.', 'MR.', 'MS.', 'MRS.', 'MAYOR', 'PRESIDENT']:
        speaker_clean = speaker_clean.replace(prefix, '').strip()

    words = speaker_clean.split()
    if words:
        # The last word is typically the last name
        return words[-1].lower()
    return speaker.lower().strip()


def merge_speaker_segments(segments: list[tuple[str, str, str, bool]]) -> dict[str, list[str]]:
    """
    Merge segments from the same speaker, handling last-name-only labels.

    Args:
        segments: List of (speaker, title, text, is_in_video_clip) tuples

    Returns:
        Dict mapping speaker names to their data
    """
    # First pass: collect full names to enable last-name lookup
    # Only consider segments that are NOT in video clips for name resolution
    known_full_names = {}  # last_name -> (full_key, display_name, title)
    for speaker, title, text, in_clip in segments:
        if is_cnn_personnel(speaker, title):
            continue
        if in_clip:
            continue  # Don't learn names from video clips

        words = speaker.strip().split()
        # Multi-word names indicate a full name (not just last name)
        if len(words) >= 2:
            last_name = extract_last_name(speaker)
            full_key = speaker.lower().strip()
            # Store the full info, preferring entries with titles
            if last_name not in known_full_names or (title and not known_full_names[last_name][2]):
                known_full_names[last_name] = (full_key, speaker.strip(), title)

    merged = {}

    for speaker, title, text, in_clip in segments:
        if is_cnn_personnel(speaker, title):
            continue
        if in_clip:
            continue  # Skip content from video clips entirely

        # Normalize speaker name using our lookup
        speaker_key, display_name = normalize_speaker_key(speaker, known_full_names)

        if speaker_key not in merged:
            merged[speaker_key] = {
                'name': display_name,  # Use the normalized display name
                'title': title,
                'segments': []
            }

        # Update name if we have a better one (full name vs last name only)
        current_name = merged[speaker_key]['name']
        if len(display_name.split()) > len(current_name.split()):
            merged[speaker_key]['name'] = display_name

        # Update title if we have a better one
        if title and not merged[speaker_key]['title']:
            merged[speaker_key]['title'] = title

        merged[speaker_key]['segments'].append(text)

    return merged


def extract_speeches(
    date: str,
    segment: int,
    party: str,
    night: int,
    min_words: int = 50
) -> list[Speech]:
    """
    Extract all speeches from a CNN transcript segment.

    Args:
        date: Date in YYYY-MM-DD format
        segment: Segment number
        party: 'Democratic' or 'Republican'
        night: Convention night (1-4)
        min_words: Minimum word count to include a speech

    Returns:
        List of Speech objects
    """
    html = fetch_transcript(date, segment)
    if not html:
        print(f"  No transcript found for {date} segment {segment}")
        return []

    raw_segments = parse_transcript(html)
    merged = merge_speaker_segments(raw_segments)

    speeches = []
    for speaker_key, data in merged.items():
        full_text = ' '.join(data['segments'])
        word_count = len(full_text.split())

        if word_count < min_words:
            continue

        speech = Speech(
            speaker=data['name'],
            title=data['title'],
            text=full_text,
            party=party,
            night=night,
            segment=segment,
            date=date,
            word_count=word_count
        )
        speeches.append(speech)

    return speeches


def save_speech(speech: Speech, output_dir: Path) -> str:
    """Save a speech to a text file. Returns the filename."""
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = speech.filename()
    filepath = output_dir / filename

    # Handle duplicates by checking if file exists with different content
    if filepath.exists():
        existing = filepath.read_text()
        if existing.strip() == speech.text.strip():
            return filename  # Same content, skip

        # Different content - append segment number
        base = filename.rsplit('.', 1)[0]
        filename = f"{base}_seg{speech.segment:02d}.txt"
        filepath = output_dir / filename

    # Format similar to existing Rev.com transcripts
    content = f"{speech.speaker} ({speech.title}):\n\n{speech.text}"
    filepath.write_text(content)

    return filename


def process_convention(
    convention: str,
    dates: list[str],
    output_dir: Path,
    segments_per_night: int = 4
) -> list[dict]:
    """
    Process all segments for a convention.

    Args:
        convention: 'DNC' or 'RNC'
        dates: List of dates in YYYY-MM-DD format
        output_dir: Directory to save extracted speeches
        segments_per_night: Max segments to try per night

    Returns:
        List of extracted speech metadata
    """
    party = 'Democratic' if convention == 'DNC' else 'Republican'
    all_speeches = []

    for night, date in enumerate(dates, 1):
        print(f"\nProcessing {convention} Night {night} ({date})...")

        for segment in range(1, segments_per_night + 1):
            print(f"  Fetching segment {segment}...")
            speeches = extract_speeches(date, segment, party, night)

            for speech in speeches:
                filename = save_speech(speech, output_dir)
                all_speeches.append({
                    'filename': filename,
                    'speaker': speech.speaker,
                    'title': speech.title,
                    'party': party,
                    'night': night,
                    'segment': segment,
                    'date': date,
                    'word_count': speech.word_count,
                    'source': 'CNN'
                })
                print(f"    Extracted: {speech.speaker} ({speech.word_count} words)")

            # Be nice to CNN's servers
            time.sleep(1)

    return all_speeches


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Extract speeches from CNN convention transcripts')
    parser.add_argument('--convention', choices=['DNC', 'RNC', 'both'], default='both',
                       help='Which convention to process')
    parser.add_argument('--output', type=Path, default=Path('data/2024/cnn'),
                       help='Output directory for extracted speeches')
    parser.add_argument('--manifest', type=Path, default=Path('data/cnn_extracted_2024.csv'),
                       help='Output manifest CSV')

    args = parser.parse_args()

    # Convention dates
    DNC_DATES = ['2024-08-19', '2024-08-20k', '2024-08-21', '2024-08-22']
    RNC_DATES = ['2024-07-15', '2024-07-16', '2024-07-17', '2024-07-18']

    all_speeches = []

    if args.convention in ('DNC', 'both'):
        speeches = process_convention('DNC', DNC_DATES, args.output)
        all_speeches.extend(speeches)

    if args.convention in ('RNC', 'both'):
        speeches = process_convention('RNC', RNC_DATES, args.output)
        all_speeches.extend(speeches)

    # Write manifest
    if all_speeches:
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        with open(args.manifest, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'filename', 'speaker', 'title', 'party', 'night',
                'segment', 'date', 'word_count', 'source'
            ])
            writer.writeheader()
            writer.writerows(all_speeches)

        print(f"\n=== Summary ===")
        print(f"Extracted {len(all_speeches)} speeches")
        print(f"Saved to: {args.output}")
        print(f"Manifest: {args.manifest}")


if __name__ == '__main__':
    main()
