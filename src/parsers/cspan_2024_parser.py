import re
import csv
import os

TRANSCRIPT_DIRECTORY = "data/raw/cspan/2024"
OUTPUT_CSV = "data/processed/parsed/parsed_cspan_2024_check.csv"
SOURCE = "CSPAN"
YEAR = 2024

FILES = {
    "dnc_2024_night_1.txt": {
        "party": "Democratic",
        "night": 1,
        "folder": "Democratic",
        "source": "https://www.c-span.org/program/campaign-2024/democratic-national-convention-day-1/647458",
    },
    "dnc_2024_night_2.txt": {
        "party": "Democratic",
        "night": 2,
        "folder": "Democratic",
        "source": "https://www.c-span.org/program/campaign-2024/democratic-national-convention-day-2/647459",
    },
    "dnc_2024_night_3.txt": {
        "party": "Democratic",
        "night": 3,
        "folder": "Democratic",
        "source": "https://www.c-span.org/program/campaign-2024/democratic-national-convention-day-3/647460",
    },
    "dnc_2024_night_4.txt": {
        "party": "Democratic",
        "night": 4,
        "folder": "Democratic",
        "source": "https://www.c-span.org/program/campaign-2024/democratic-national-convention-day-4/647461",
    },
    "rnc_2024_night_1.txt": {
        "party": "Republican",
        "night": 1,
        "folder": "Republican",
        "source": "https://www.c-span.org/program/campaign-2024/republican-national-convention-day-1-evening-session/644645",
    },
    "rnc_2024_night_2.txt": {
        "party": "Republican",
        "night": 2,
        "folder": "Republican",
        "source": "https://www.c-span.org/program/campaign-2024/republican-national-convention-day-2/644518",
    },
    "rnc_2024_night_3.txt": {
        "party": "Republican",
        "night": 3,
        "folder": "Republican",
        "source": "https://www.c-span.org/program/campaign-2024/republican-national-convention-day-3/644519",
    },
    "rnc_2024_night_4.txt": {
        "party": "Republican",
        "night": 4,
        "folder": "Republican",
        "source": "https://www.c-span.org/program/campaign-2024/republican-national-convention-day-4/644520",
    },
}

TIMESTAMP_RE = re.compile(r"^\d{2}:\d{2}:\d{2}$")


def split_into_blocks(lines):
    blocks = []
    current_timestamp = None
    current_lines = []

    for line in lines:
        line = line.strip()

        if not line or line == "Show More":
            continue

        if TIMESTAMP_RE.match(line):
            if current_timestamp is not None:
                blocks.append((current_timestamp, current_lines))
            current_timestamp = line
            current_lines = []
        else:
            current_lines.append(line)

    if current_timestamp is not None:
        blocks.append((current_timestamp, current_lines))

    return blocks


def read_transcript(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    return split_into_blocks(lines)


def clean_speech_text(text):
    if not text:
        return ""

    noise_patterns = [
        r"\bAPPLAUSE AND CLAP\b",
        r"\bCHEERS AND APPLAUSE\b",
        r"\bCROWD CHANTING\b",
        r"\bCROWD CHANT\b",
        r"\bCROWD CHEERING\b",
        r"\bAPPLAUSE\b",
        r"\bCHEERS\b",
        r"\bCHEERING\b",
        r"\bCLAP\b",
        r"\bCLAPPING\b",
        r"\bLAUGHTER\b",
        r"\bNO AUDIO\b",
        r"♪+",
    ]

    for pattern in noise_patterns:
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE)

    text = re.sub(r"\s+", " ", text).strip()
    return text


def is_bad_speaker_label(line):
    clean = line.strip().upper().strip(' "\'.!?,-')

    bad_exact = {
        "WE LOVE YOU",
        "THANK YOU",
        "LET'S GO",
        "LETS GO",
        "USA",
        "HELLO",
        "GOOD EVENING",
        "GOOD NIGHT",
    }

    bad_starts = (
        "LADIES AND GENTLEMEN",
        "PLEASE WELCOME",
        "AND NOW",
        "HOW DO YOU CAST YOUR VOTE",
        "MY NAME IS",
        "THANK YOU",
        "GOOD EVENING",
        "GOOD NIGHT",
    )

    if clean in bad_exact:
        return True

    if clean.startswith(bad_starts):
        return True

    return False


def looks_like_speaker_line(line):
    clean = line.strip()

    if not clean:
        return False

    if is_bad_speaker_label(clean):
        return False

    words = clean.split()

    if len(words) > 6:
        return False

    if clean.isupper():
        return True

    alpha_words = [w for w in words if any(ch.isalpha() for ch in w)]
    if alpha_words and all(w[0].isupper() for w in alpha_words if w[0].isalpha()):
        return True

    return False


def extract_speaker_and_text(block_lines):
    if not block_lines:
        return None, "", 0

    speaker = None
    speaker_index = None

    for i, line in enumerate(block_lines[:3]):
        clean = line.strip()

        if looks_like_speaker_line(clean):
            speaker = clean
            speaker_index = i
            break

    if speaker is None:
        return None, "", 0

    speech_lines = block_lines[speaker_index + 1:]
    text = " ".join(speech_lines).strip()
    text = clean_speech_text(text)
    word_count = len(text.split())

    if not text:
        return None, "", 0

    return speaker, text, word_count


def parse_file(file_name):
    info = FILES[file_name]

    file_path = os.path.join(
        TRANSCRIPT_DIRECTORY,
        info["folder"],
        file_name
    )

    blocks = read_transcript(file_path)
    rows = []

    for timestamp, lines in blocks:
        speaker, text, word_count = extract_speaker_and_text(lines)

        if not speaker or not text:
            continue

        rows.append({
            "speaker": speaker,
            "party": info["party"],
            "year": YEAR,
            "night": info["night"],
            "timestamp": timestamp,
            "speech": text,
            "word_count": word_count,
            "source": SOURCE,
            "source_file": info["source"],
        })

    return rows


def parse_all_files():
    all_rows = []

    for file_name in FILES:
        rows = parse_file(file_name)
        all_rows.extend(rows)

    return all_rows


def save_to_csv(rows, output_csv):
    os.makedirs(os.path.dirname(output_csv), exist_ok=True)

    fieldnames = [
        "speaker",
        "party",
        "year",
        "night",
        "timestamp",
        "speech",
        "word_count",
        "source",
        "source_file",
    ]

    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    rows = parse_all_files()
    save_to_csv(rows, OUTPUT_CSV)
    print(f"Saved {len(rows)} rows to {OUTPUT_CSV}")