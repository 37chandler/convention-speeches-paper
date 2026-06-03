#!/usr/bin/env python3
"""
Rev.com 2024 Convention Transcript Parser

Single-speaker files. Speaker name extracted from filename.
DNC filenames contain no night number — resolved via lookup table.
RNC filenames contain night explicitly (night_one, night_two, etc.).
Some RNC filenames also have no night number — resolved via RNC lookup table.

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


# ── DNC night lookup ──────────────────────────────────────────────────────────
# DNC filenames have no night number. Hardcoded from the 2024 DNC schedule.

DNC_NIGHT_LOOKUP: dict[str, int] = {
    "adam_kinzinger":               3,
    "al_sharpton":                  1,
    "alexandria_ocasio_cortez":     1,
    "ashley_biden":                 4,
    "barack_obama":                 2,
    "bernie_sanders":               2,
    "bill_clinton":                 3,
    "chuck_schumer":                2,
    "cory_booker":                  1,
    "d_l_hughley":                  4,
    "debbie_wasserman_schultz":     1,
    "dick_durbin":                  1,
    "doug_emhoff":                  2,
    "elizabeth_warren":             2,
    "gretchen_whitmer":             4,
    "hakeem_jeffries":              3,
    "hillary_rodham_clinton":       1,
    "jaime_harrison":               1,
    "jill_biden":                   1,
    "kamala_harris":                4,
    "kathy_hochul":                 2,
    "michelle_obama":               2,
    "nancy_pelosi":                 1,
    "oprah_winfrey":                3,
    "pete_buttigieg":               3,
    "president_biden":              1,
    "raphael_warnock":              1,
    "tim_walz":                     3,
    "uaw_president_shawn_fain":     1,
}

# ── RNC night lookup ──────────────────────────────────────────────────────────
# RNC speakers whose filenames have no night number.

RNC_NIGHT_LOOKUP: dict[str, int] = {
    "donald_trump": 4,
}

# ── Exclusions ────────────────────────────────────────────────────────────────
# Filenames that are news video titles or non-convention speeches.

EXCLUDE_FILES: set[str] = {
    "harris_energizes_crowd_with_tribute_to_biden_in_dnc_entrance.txt",
    "j_d_vance_nominated_as_vice_presidential_nominee_at_the_rnc.txt",
    "secret_service_briefing_ahead_of_rnc.txt",
    "biden_speaks_during_the_115th_naacp_national_convention.txt",
}

# ── Name fixes ────────────────────────────────────────────────────────────────
# Applied after extraction — catches cases the filename parser can't handle.

NAME_FIXES: dict[str, str] = {
    "Alexandria Ocasio Cortez":                                    "Alexandria Ocasio-Cortez",
    "Hillary Rodham Clinton At The Democratic National Convention": "Hillary Clinton",
    "Jaime Harrison Democratic National Convention 2024 Rev":      "Jaime Harrison",
    "Jd Vance Speaks At Rnc Night 3":                              "J.D. Vance",
    "J.D. Vance Speaks":                                           "J.D. Vance",
    "President Biden Addresses Democratic National Convention":    "Joe Biden",
    "President Biden":                                             "Joe Biden",
    "Uaw President Shawn Fain":                                    "Shawn Fain",
    "Ron Desantis":                                                "Ron DeSantis",
    "Don Trump Jr.":                                               "Donald Trump Jr.",
    "Don Trump Jr":                                                "Donald Trump Jr.",
    "Dr. Ben Carson":                                              "Ben Carson",
    "Linda Mcmahon":                                               "Linda McMahon",
}


# ── Speech-start markers ──────────────────────────────────────────────────────
# For speakers whose transcripts open with non-speech content (song lyrics,
# host intro noise that survives the general stripper, etc.), map the speaker
# name to a substring that marks where their actual speech begins.

SPEECH_START_MARKERS: dict[str, str] = {
    # Jackie Wilson "Higher and Higher" lyrics precede Biden's real speech.
    "Joe Biden":        "to my dearest daughter",
    # Sara Bareilles "Brave" lyrics + Thank you opener precede Clinton's speech.
    # "Something, something is happening" is where her real content starts.
    "Hillary Clinton":  "Something, something is happening",
    # Kamala Harris: large crowd-response opener; real speech begins here.
    "Kamala Harris":    "So let me start by thanking",
    # Jill Biden: "Thank you so much. Love you too." crowd noise at very start.
    "Jill Biden":       "Joe and I have been together",
    # Michelle Obama: host intro + crowd opener block precedes real speech.
    "Michelle Obama":   "Something wonderfully magical",
    # Barack Obama: Thank you / Hello crowd-response opener block.
    "Barack Obama":     "Chicago, it\u2019s good to be home",
}

# ── Crowd chant block patterns ────────────────────────────────────────────────
# Phrases that appear as audience chant blocks transcribed mid-speech.
# Each pattern matches 2+ consecutive repetitions of a crowd phrase.
# Order matters: longer/more-specific patterns first.

CROWD_BLOCK_PATTERNS: list[str] = [
    # Slogans / call-and-response
    r"(?:We love Trump[.!]?\s*){2,}",
    r"(?:We love Joe[.!]?\s*){2,}",
    r"(?:Lock (?:him|her) up[.!]?\s*){2,}",
    r"(?:Trump's a scab[,.]?\s*){2,}",
    r"(?:Union Joe[.!]?\s*){2,}",
    r"(?:Four more years[.!]?\s*){2,}",
    r"(?:Yes,? she can[.!]?\s*){2,}",
    r"(?:Yes we are[.!]?\s*){2,}",
    r"(?:Yes,? you are[.!]?\s*){2,}",
    r"(?:We'?re not going back[.!]?\s*){2,}",
    r"(?:Keep going[.!]?\s*){2,}",
    r"(?:Build (?:the|our) wall[.!]?\s*){2,}",
    r"(?:Thank you,? Joe[.!]?\s*){2,}",
    r"(?:Thank you,? Jill[.!]?\s*){2,}",
    r"(?:Thank you,? Kamala[.!]?\s*){2,}",
    # Single-word name/slogan chants — ASCII and hyphenated variants
    r"(?:USA[.!]?\s*){2,}",
    r"(?:U-S-A[.!]?\s*){2,}",           # hyphenated variant (e.g. Hulk Hogan)
    r"(?:Trump[.!]?\s*){2,}",
    r"(?:Fight[.!]?\s*){2,}",
    r"(?:Whoo[.!]?\s*){2,}",
    # Speaker-name chants (crowd chanting the speaker's own name)
    r"(?:Kari[.,!]?\s*){2,}",
    r"(?:Kathy[.,!]?\s*){2,}",
    r"(?:Warnock[.,!]?\s*){2,}",
    r"(?:Bernie[.,!]?\s*){2,}",
    r"(?:Corey[.,!]?\s*){2,}",
    r"(?:JD[.,!]?\s*){2,}",
]

# ── Inline crowd-burst fixes ──────────────────────────────────────────────────
# Precise surgical replacements for crowd noise injected mid-sentence.
# Each entry: (regex_pattern, replacement_string)

INLINE_CROWD_FIXES: list[tuple[str, str]] = [
    # Hillary: transcript cuts off "34 felony convictions" mid-sentence then
    # crowd "Lock him up" block interrupts before speech resumes.
    (
        r"with 34 As vice president,\s*(?:Lock him up[.!]?\s*)+But we also know as vice president,",
        "with 34 felony convictions. But we also know as vice president,",
    ),
    # Trump: keep his quoted "Fight, fight, fight." (his own words);
    # strip only the crowd echo repetitions that immediately follow.
    (
        r'("Fight, fight, fight\."\s*)(?:Fight, fight, fight\.\s*)+',
        r"\1",
    ),
    # Trump Jr.: comma-separated fight chain "fight, fight, fight, fight, ..."
    # not caught by period-anchored collapse; crowd chanting after assassination
    # attempt description. Keep nothing — his own sentence follows separately.
    (
        r"(?:fight,\s*){3,}fight[.,!]?",
        "",
    ),
    # Guilfoyle: ", Whoo." crowd burst inserted mid-sentence.
    (r",\s*Whoo\.\s*", " "),
    # Durbin: "Hey! Whoo! Yes, hello, [state]." crowd interjection mid-sentence.
    (r",?\s*Hey!\s*Whoo!\s*Yes,\s*hello,\s*\w+\.?\s*", " "),
    # Trump: transcript fragment "I\u2019" (curly apostrophe) before crowd block.
    (r"\bI\u2019\s+(?=Yes, you are)", "I "),
    # Trump: ASCII fallback for same fragment.
    (r"\bI'\s+(?=Yes, you are)", "I "),
    # Biden: "It\u2019" fragment (curly apostrophe) + crowd "Thank you!" block.
    # Removes the truncated fragment and the entire crowd chant that follows.
    (
        r"It\u2019\s*(?:Thank you[!,]?\s*(?:Kamala[,]?\s*)?){2,}",
        "",
    ),
    # Biden: lone "Boo!" crowd interjection between two quoted sentences.
    (r"\bBoo!\s*", ""),
    # Bernie Sanders: "\n" newline artifact collapsed to "n" during whitespace
    # normalisation → "honor-nIt is an honor". Restore as two sentences.
    (r"honor-nIt is an honor", "honor. It is an honor"),
    # Guilfoyle: missing space/period after "prayer" before next sentence.
    (r"in prayer(?=\s*[A-Z])", "in prayer."),
    # J.D. Vance: "JD's mom!" chanted 3× by crowd; keep one, remove extras.
    # Curly apostrophe (U+2019) is used throughout these transcripts.
    (r"(JD\u2019s mom[!.]?\s*)(?:JD\u2019s mom[!.]?\s*)+", r"\1"),
    (r"(JD's mom[!.]?\s*)(?:JD's mom[!.]?\s*)+", r"\1"),   # ASCII fallback
    # Tim Scott: "Disgusting. Disgusting." — crowd chant response; keep one.
    (r"\b(Disgusting[.!]?)\s+Disgusting[.!]?", r"\1"),
    # Tim Walz: curly-quote call-and-response chant × 3 → keep one exchange.
    (
        r'(?:\u201cWhen we fight\u2026\u201d\s*\u201cWe win\.\u201d\s*){2,}',
        "\u201cWhen we fight\u2026\u201d \u201cWe win.\u201d ",
    ),
    # Tim Walz: Neil Young "Keep on Rockin'" lyric fragment at speech end.
    # Curly apostrophe variant; re.DOTALL so it eats to end of string.
    (
        r"Keep on rockin[\u2019']? in the free world\.?.*$",
        "",
    ),
    # AOC: duplicate opening sentence pair (slight punctuation difference each
    # time) — strip the first, unpunctuated version.
    (
        r"^Thank you Chicago for your energy\. "
        r"Thank you Kamala Harris and Tim Walz for your vision\.\s*"
        r"Thank you\.\s*",
        "",
    ),
    # ── Dangling fragment artifacts ───────────────────────────────────────────
    # When a crowd-noise block is removed mid-sentence, the partial word before
    # it is left stranded ending in a curly apostrophe (U+2019). Each fix
    # below drops the fragment and repairs the surrounding text.
    #
    # Donald Trump: "took him out. I\u2019 Yes, Thank you. But I\u2019m not."
    # "I\u2019" is the start of "I\u2019m not supposed to be here" cut short by
    # the crowd "Yes, you are!" block. Drop fragment + "Yes, Thank you." residue.
    (r"I\u2019\s+Yes,\s+Thank you\.\s*", ""),
    # Shawn Fain: "Harris is one of us. She\u2019 [scab chant x7] Trump\u2019"
    # "She\u2019" and trailing "Trump\u2019" are both fragment ends. Remove the
    # entire run — real content resumes at "That\u2019s not just my opinion".
    (
        r"She\u2019\s+(?:Trump\u2019s a scab[,.]?\s*)+Trump\u2019\s+",
        " ",
    ),
    # Kimberly Guilfoyle: "Donald Trump\u2019 Whoo. … strong, safe, Yeah. Whoo."
    # "Trump\u2019" ends a truncated sentence; three crowd bursts follow.
    # Reconstruct by joining the two surrounding sentences.
    (
        r"Donald Trump\u2019\s+Whoo\.\s+"
        r"Donald Trump will once again make our country strong,\s+safe,\s+Yeah\.\s+Whoo\.\s+",
        "Donald Trump will once again make our country strong, safe, ",
    ),
    # Kimberly Guilfoyle: "vulnerable But Joe just couldn\u2019 Yeah. Whoo."
    (r",\s+vulnerable But Joe just couldn\u2019\s+Yeah\.\s+Whoo\.\s+", ", vulnerable. "),
    # Kimberly Guilfoyle: "they don\u2019 Whoo." — "don\u2019" = "don't"
    (r"they don\u2019\s+Whoo\.\s+", "they "),
    # Kimberly Guilfoyle: isolated crowd bursts (single Whoo/Yeah instances)
    # that survived because they weren't part of a 2+ repeat block.
    (r",\s+Yes\.\s+Whoo\.\s+", ", "),               # "in my life, Yes. Whoo."
    (r",\s+Yeah\.\s+Whoo\.\s+(?=We will restore)", ". "),  # "abroad, Yeah. Whoo."
    (r":\s+Whoo\.\s+USA\.\s+", ". "),               # "to know this: Whoo. USA."
    (r"\?\s+Whoo\.\s+", "? "),                       # "for President Trump? Whoo."
    # Marjorie Taylor Greene: "we are made in God\u2019 Amen."
    # "God\u2019" = "God's" cut short. Reconstruct + remove crowd "Amen."
    (r"we are made in God\u2019\s+Amen\.\s+", "we are made in God's image. "),
    # Joe Biden: "America\u2019s winning and the world\u2019 Guess what?"
    # "world\u2019" = "world\u2019s" cut short. Drop fragment; "Guess what?"
    # is Biden's own next sentence.
    (r"the world\u2019\s+(?=Guess what\?)", ""),
    # Tucker Carlson: "fellow citizens OD\u2019 Yeah, actually."
    # "OD\u2019" = "OD\u2019ing" cut short. Reconstruct; "Yeah, actually." is
    # Tucker's own commentary — keep it.
    (r"fellow citizens OD\u2019\s+", "fellow citizens overdosing. "),
    # Tucker Carlson: lone crowd "Yeah." between two of his own sentences.
    (r"(in World War II\.)\s+Yeah\.\s+(Our bloodiest war)", r"\1 \2"),
    # Chuck Schumer: "let me hear you if you\u2019 Friends,"
    # "you\u2019" = "you\u2019re with me" or similar, cut short. Drop fragment.
    (r"if you\u2019\s+(?=Friends,)", ""),
    # Pete Buttigieg: "Indiana mayor, Thank you. Thank you." host-intro residue.
    # The Please-welcome regex stops at commas in multi-part titles; strip
    # the remainder with a dedicated pattern.
    (r"^Indiana mayor,\s*(?:Thank you[.!]?\s*)+", ""),
    # Raphael Warnock: "We\u2019re not going back." appears 3× with two bare
    # "We\u2019 " stubs and an ellipsis between them — crowd chanting broke
    # his rhetorical phrase mid-repetition. Collapse to two clean instances.
    (
        r"(We\u2019re not going back\.)\s+We\u2019\s+"
        r"(We\u2019re not going back\.)\s+We\u2019re not going back\.\s+We\u2019\s+\u2026\s+",
        r"\1 \2 ",
    ),
    # Chuck Schumer: fragment fix dropped "if you\u2019" but left "hear you
    # Friends," with a missing word boundary. Insert period to bridge.
    (r"hear you\s+Friends,", "hear you. Friends,"),
    # Hillary Clinton: "Something we\u2019" — a cut-off sentence stub left
    # after the opener was stripped. "First though," is real speech.
    (r"Something we\u2019\s+(?=First though,)", ""),
]

# ── Opening crowd-noise pattern ───────────────────────────────────────────────
# Matches runs of crowd-response filler at the very start of a speech
# (Thank you / Wow / Hello / Good evening / etc.) before real content begins.

_OPENER_TOKENS = (
    r"Thank you[,!.]?(?:\s+(?:so much|everyone|all|guys))?[,!.]?"
    r"|Thank you,\s+(?:Joe|Jill|Kamala)[!.]?"
    r"|Wow[!.]?"
    r"|Hello[,!.]?"
    r"|Good evening[,!.]?"
    r"|I love you[,!.]?"
    r"|Love you too[,!.]?"
    r"|Oh my goodness[,!.]?"
    r"|Okay[,!.]?"
    r"|All right[,!.]?"
    r"|Yeah[,!.]?"                 # Shawn Fain / Michelle Obama opener noise
    r"|Please[.!]?"
    r"|California[.!]?"            # Harris walk-on intro noise
    r"|We got a big night ahead[.!]?"  # Michelle Obama host-line residue
)
_OPENER_PAT = re.compile(
    r"^(?:" + _OPENER_TOKENS + r")(?:\s+(?:" + _OPENER_TOKENS + r"))*\s*",
    re.IGNORECASE,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def extract_speaker_from_filename(filename: str) -> str:
    name = filename.replace(".txt", "")

    suffixes = [
        "_speaks_at_2024_democratic_national_convention",
        "_speaks_at_2024_dnc",
        "_speaks_at_the_democratic_national_convention",
        "_speaks_at_democratic_national_convention",
        "_speaks_at_dnc",
        "_speaks_at_2024_republican_national_convention",
        "_speaks_at_rnc_2024_night_one",
        "_speaks_at_rnc_2024_night_two",
        "_speaks_at_rnc_2024_night_three",
        "_speaks_at_rnc_2024_night_four",
        "_speaks_at_rnc_2024",
        "_speaks_at_the_rnc",
        "_speaks_at_rnc",
        "_speaks_at_rnc_night_3",
        "_speaks_during_the_115th_naacp_national_convention",
        "_at_the_democratic_national_convention",
        "_democratic_national_convention_2024_rev",
        "_addresses_democratic_national_convention",
        "_at_rnc_night_3",
    ]

    for suffix in suffixes:
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break

    name = name.replace("_", " ")
    name = " ".join(word.capitalize() for word in name.split())

    name = name.replace("D L ", "D.L. ")
    name = name.replace("Jd ", "J.D. ")
    name = name.replace("Jr ", "Jr. ")
    name = name.replace("Dr ", "Dr. ")

    return name.strip()


def extract_party_from_filename(filename: str) -> str:
    f = filename.lower()
    if "dnc" in f or "democratic" in f:
        return "Democratic"
    if "rnc" in f or "republican" in f:
        return "Republican"
    return "Unknown"


def get_speaker_key(filename: str) -> str:
    """Extract the speaker prefix from filename for night lookup."""
    name = filename.replace(".txt", "").lower()
    for suffix in [
        "_speaks_at", "_at_the", "_addresses_", "_at_rnc",
        "_democratic_national", "_energizes_", "_nominated_",
    ]:
        idx = name.find(suffix)
        if idx != -1:
            return name[:idx]
    return name


def extract_night_from_filename(filename: str, speaker_key: str, party: str) -> int:
    f = filename.lower()

    if "night_one" in f or "night_1" in f:
        return 1
    if "night_two" in f or "night_2" in f:
        return 2
    if "night_three" in f or "night_3" in f:
        return 3
    if "night_four" in f or "night_4" in f:
        return 4

    if party == "Democratic":
        return DNC_NIGHT_LOOKUP.get(speaker_key, 0)

    if party == "Republican":
        return RNC_NIGHT_LOOKUP.get(speaker_key, 0)

    return 0


def _strip_to_speech_start(speaker: str, text: str) -> str:
    """
    For speakers whose transcripts open with non-speech content (song lyrics,
    host-intro residue, crowd noise blocks), fast-forward to the marker that
    signals the true start of the speech.

    For song-lyric cases the marker may land mid-paragraph, so we walk back
    to the nearest sentence boundary to avoid orphaning a fragment.
    For all other cases we cut directly at the marker.
    """
    marker = SPEECH_START_MARKERS.get(speaker)
    if not marker:
        return text
    idx = text.find(marker)
    if idx == -1:
        return text
    # Song-lyric openers: walk back to nearest "." to avoid mid-sentence cut.
    if speaker in ("Joe Biden", "Hillary Clinton"):
        cut = text[:idx].rfind(".")
        return text[cut + 1 :].strip() if cut != -1 else text[idx:].strip()
    # All other markers: cut directly — the marker IS the first real sentence.
    return text[idx:].strip()


def _collapse_chant_repeats(text: str, min_reps: int = 3) -> str:
    """
    Collapse any phrase repeated min_reps+ times consecutively down to one
    instance. Iterates until stable so nested/adjacent repetitions are caught.
    """
    pattern = re.compile(
        r"((?:[A-Z'\"\u201c][^\n.!?]{0,58}[.!?]\s*){1,2})(?:\1){%d,}" % (min_reps - 1)
    )
    prev = None
    while prev != text:
        prev = text
        text = pattern.sub(lambda m: m.group(1).rstrip(), text)
    return text


def _strip_crowd_blocks(text: str) -> str:
    """Remove all crowd chant block patterns (2+ consecutive repetitions)."""
    for pat in CROWD_BLOCK_PATTERNS:
        text = re.sub(pat, " ", text, flags=re.IGNORECASE)
    return text


def _apply_inline_fixes(text: str, flags_dotall: set[str] | None = None) -> str:
    """
    Apply surgical inline replacements for crowd bursts, artifacts, and song
    lyric fragments mid-text.

    flags_dotall: set of pattern strings that require re.DOTALL (consume to
    end-of-string). All other patterns use re.IGNORECASE only.
    """
    dotall_pats = flags_dotall or set()
    for pat, repl in INLINE_CROWD_FIXES:
        flags = re.IGNORECASE | re.DOTALL if pat in dotall_pats else re.IGNORECASE
        text = re.sub(pat, repl, text, flags=flags)
    return text


def _strip_opening_crowd_noise(text: str) -> str:
    """
    Strip leading runs of crowd-response filler (Thank you / Wow / Hello /
    Good evening / etc.) that precede the actual speech content.
    Only strips when the block is substantial (> 15 chars) to avoid
    removing a genuine short opener like a single "Thank you."
    """
    m = _OPENER_PAT.match(text)
    if m and m.end() > 15:
        return text[m.end() :].strip()
    return text


def clean_text(text: str, speaker: str = "") -> str:
    # ── Normalise line endings ────────────────────────────────────────────────
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # ── Remove speaker/timestamp labels like "Speaker Name (12:34):" ─────────
    text = re.sub(r"[A-Za-z\s.'-]+\(\d{1,2}:\d{2}\):", "", text)

    # ── Remove standalone timestamps "(12:34)" or "(1:02:33)" ────────────────
    text = re.sub(r"\(\d{1,2}:\d{2}(?::\d{2})?\)", "", text)

    # ── Remove [inaudible ...] markers ───────────────────────────────────────
    text = re.sub(r"\[inaudible[^\]]*\]\.?", "", text, flags=re.IGNORECASE)

    # ── Remove all bracketed stage directions / crowd noise tags ─────────────
    text = re.sub(r"\[[^\]]{0,120}\]", "", text)

    # ── Remove inline crowd/noise labels ─────────────────────────────────────
    text = re.sub(
        r"\b(applause|cheers?|cheering|laughter|crowd chanting|audience noise|"
        r"music|crosstalk|booing|chanting)\b[.!,:; -]*",
        "",
        text,
        flags=re.IGNORECASE,
    )

    # ── Remove "Speaker N" labels ─────────────────────────────────────────────
    text = re.sub(r"\bSpeaker \d+\b\s*", "", text, flags=re.IGNORECASE)

    # ── Remove intro/host lines ───────────────────────────────────────────────
    # Match "Please welcome … [title/name]," — the host line ends with a comma
    # (announcer hands off to speaker) rather than a period, so we match up to
    # the first comma that is followed only by whitespace / thank-you noise,
    # then also eat the crowd-response filler that immediately follows.
    text = re.sub(
        r"^Please welcome\b.{0,160}?,\s*(?:(?:Thank you|All right|Yeah|Okay|Hello)[.!,]?\s*)*",
        "",
        text,
        flags=re.IGNORECASE,
    )
    # Fallback: period-terminated host lines (older pattern, keep for safety)
    text = re.sub(r"Please welcome[^.\n]{0,120}\.\s*", "", text, flags=re.IGNORECASE)

    # ── Remove ALL-CAPS anthem / song lines ──────────────────────────────────
    text = re.sub(r"(?m)^[A-Z ,.''\-]{10,}$\n?", "", text)

    # ── Remove known anthem / lyric phrases ──────────────────────────────────
    text = re.sub(
        r"(?i)\b(star[- ]spangled banner|land of the free|home of the brave|"
        r"o say can you see)\b.*",
        "",
        text,
    )

    # ── Strip to true speech start (song lyrics, host residue, crowd openers) ──
    text = _strip_to_speech_start(speaker, text)

    # ── Collapse chant repetitions (3+ → 1) ──────────────────────────────────
    text = _collapse_chant_repeats(text, min_reps=3)

    # ── Remove crowd chant blocks (2+ consecutive crowd phrases) ─────────────
    text = _strip_crowd_blocks(text)

    # ── Surgical inline fixes (mid-sentence bursts, artifacts, song lyrics) ──
    text = _apply_inline_fixes(text, flags_dotall={
        # These patterns need re.DOTALL to consume to end-of-string
        r"Keep on rockin[\u2019']? in the free world\.?.*$",
    })

    # ── Strip leading crowd-response filler ──────────────────────────────────
    text = _strip_opening_crowd_noise(text)

    # ── Remove ellipsis fragments at start ───────────────────────────────────
    text = re.sub(r"^\s*…\s*", "", text)

    # ── Final whitespace / punctuation cleanup ────────────────────────────────
    text = re.sub(r"\n{2,}", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" ([.,!?])", r"\1", text)          # no space before punctuation
    text = re.sub(r"\.(?=[A-Z])", ". ", text)          # space after period
    text = re.sub(r"\.\s*\.", ".", text)               # collapse double periods
    text = re.sub(r"^\W+\s*", "", text)               # strip leading non-word chars
    text = re.sub(r"\s+", " ", text).strip()

    return text


# ── Core ──────────────────────────────────────────────────────────────────────

def parse_rev_2024_file(filepath: Path) -> Speech | None:
    if filepath.name in EXCLUDE_FILES:
        return None

    content = filepath.read_text(encoding="utf-8", errors="replace")
    speaker = extract_speaker_from_filename(filepath.name)
    speaker = NAME_FIXES.get(speaker, speaker)

    party = extract_party_from_filename(filepath.name)
    speaker_key = get_speaker_key(filepath.name)
    night = extract_night_from_filename(filepath.name, speaker_key, party)

    # Pass speaker name so clean_text can apply speaker-specific rules.
    text = clean_text(content, speaker=speaker)
    word_count = len(text.split())

    return Speech(
        speaker=speaker,
        party=party,
        year=2024,
        night=night,
        timestamp="",
        text=text,
        word_count=word_count,
        source_file=filepath.name,
        source="REV",
    )


def process_all_rev_2024(data_dir: Path, output_path: Path) -> list[dict]:
    FIELDNAMES = [
        "speaker", "party", "year", "night", "timestamp",
        "text", "word_count", "source_file", "source",
    ]

    all_speeches = []

    for filepath in sorted(data_dir.glob("*.txt")):
        speech = parse_rev_2024_file(filepath)
        if speech is None:
            print(f"  EXCLUDED: {filepath.name}")
            continue

        print(f"  {speech.speaker} | {speech.party} | Night {speech.night} | {speech.word_count} words")
        all_speeches.append({f: getattr(speech, f) for f in FIELDNAMES})

    if all_speeches:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writeheader()
            writer.writerows(all_speeches)
        print(f"\nWrote {len(all_speeches)} speeches → {output_path}")

    return all_speeches


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=Path("data/raw/rev/2024"))
    ap.add_argument("--output",   type=Path, default=Path("data/processed/parsed/parsed_rev_2024.csv"))
    args = ap.parse_args()
    process_all_rev_2024(args.data_dir, args.output)


if __name__ == "__main__":
    main()