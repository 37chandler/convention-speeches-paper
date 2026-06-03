import re
import csv
import os

TRANSCRIPT_FILE = os.path.join("data", "raw", "youtube", "rnc_night_1.txt")
OUTPUT_FILE = os.path.join("data", "processed", "parsed", "rnc_night_1_missing_speakers.csv")

SOURCE = "YOUTUBE"
SOURCE_FILE = "https://www.youtube.com/watch?v=8q787ba_kao"
YEAR = 2024
PARTY = "Republican"
NIGHT = 1

SPEAKERS = [
    {
        "speaker": "Kristi Noem",
        "speech_start": 133,
        "speech_end": 143,
        "stop_phrase": "donald trump's surprise visit",
    },
    {
        "speaker": "Robert Bartels",
        "speech_start": 145,
        "speech_end": 149,
        "stop_phrase": "please welcome congressman byron",
    },
    {
        "speaker": "Byron Donalds",
        "speech_start": 149,
        "speech_end": 156,
        "stop_phrase": "new york. new york.",
        "trim_before": "Good evening, Milwaukee.",
    },
    {
        "speaker": "David Sacks",
        "speech_start": 162,
        "speech_end": 168,
        "stop_phrase": "Please welcome women's advocate Vanessa",
    },
    {
        "speaker": "Vanessa Faura",
        "speech_start": 168,
        "speech_end": 172,
        "stop_phrase": "ladies and gentlemen, charlie kirk",
        "trim_before": "Wow, you all look wonderful.",
    },
    {
         "speaker": "Charlie Kirk",
        "speech_start": 172,
        "speech_end": 180,
        "stop_phrase": "ladies and gentlemen, please welcome the",
        "trim_before": "Thank you everybody. Thank you.",

    },
]

NOISE_PREFIXES = (
    "[",
    "ladies and gentlemen",
    "please welcome",
    "of the all-in podcast",
    "governor christy gnome",
    "governor christine gnome",
    "heat. ",
    "heat! ",
    "usa.",
)

LINE_RE = re.compile(r"^(\d+):(\d+)\s+(.+)$")


def format_timestamp(minute):
    if minute is None:
        return ""
    hours = minute // 60
    mins = minute % 60
    return f"{hours:02d}:{mins:02d}:00"


def is_noise(text):
    tl = text.lower().strip()

    for prefix in NOISE_PREFIXES:
        if tl.startswith(prefix):
            return True

    if tl.startswith("[") and tl.endswith("]"):
        return True

    return False


def clean_text(text):
    if not text:
        return ""

    noise_patterns = [
        r"\[.*?\]",
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


def trim_speech_start(speech, speaker_info):
    trim_before = speaker_info.get("trim_before")
    if not trim_before:
        return speech

    idx = speech.lower().find(trim_before.lower())
    if idx != -1:
        return speech[idx:].strip()

    return speech


def parse_segments(raw):
    segments = []

    for line in raw.splitlines():
        m = LINE_RE.match(line.strip())
        if m:
            minute = int(m.group(1))
            second = int(m.group(2))
            text = m.group(3).strip()
            if text:
                segments.append((minute, second, text))

    return segments


def extract_speech(segments, speaker_info):
    start = speaker_info["speech_start"]
    end = speaker_info["speech_end"]
    stop = speaker_info["stop_phrase"].lower()

    collecting = False
    parts = []
    first_minute = None
    first_second = None

    for minute, second, text in segments:
        tl = text.lower().strip()

        if not collecting and minute >= start:
            collecting = True

        if not collecting:
            continue

        if stop and stop in tl:
            break

        if minute > end:
            break

        if is_noise(text):
            continue

        if first_minute is None:
            first_minute = minute
            first_second = second

        parts.append(text.strip())

    speech = clean_text(" ".join(parts))
    speech = trim_speech_start(speech, speaker_info)

    if speaker_info["speaker"] == "Vanessa Faura":
        idx = speech.lower().find("wow, you all look wonderful.")
        if idx != -1:
            first_minute = 169
            first_second = 2

    return speech, first_minute, first_second


def main():
    print("Reading:", TRANSCRIPT_FILE)

    with open(TRANSCRIPT_FILE, encoding="utf-8") as f:
        raw = f.read()

    segments = parse_segments(raw)
    rows = []

    for spk in SPEAKERS:
        speech, first_minute, first_second = extract_speech(segments, spk)
        word_count = len(speech.split())

        timestamp = ""
        if first_minute is not None and first_second is not None:
            hours = first_minute // 60
            mins = first_minute % 60
            timestamp = f"{hours:02d}:{mins:02d}:{first_second:02d}"

        rows.append({
            "speaker": spk["speaker"],
            "party": PARTY,
            "year": YEAR,
            "night": NIGHT,
            "timestamp": timestamp,
            "speech": speech,
            "word_count": word_count,
            "source": SOURCE,
            "source_file": SOURCE_FILE,
        })

        print("-" * 60)
        print("Speaker   :", spk["speaker"])
        print("Timestamp :", timestamp)
        print("Words     :", word_count)
        print("Preview   :", speech[:150])

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

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

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print("-" * 60)
    print(f"Saved {len(rows)} rows to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()