# We vs. I: Collective and Individual Framing in U.S. Presidential Convention Speeches, 2004–2024

An NLP analysis of first-person pronoun usage across 1,800 convention speeches to measure collective vs. individual framing by party and incumbency status.

---

## Pipeline

```
RAW TRANSCRIPTS
(CSPAN 2004–2016, Rev 2020, CSPAN + Rev + CNN + YouTube 2024)
        │
        ▼
    make parse
    ├── src/parsers/cspan_parser.py          2004–2016 CSPAN
    ├── src/parsers/cspan_2024_parser.py     2024 CSPAN
    ├── src/parsers/rev_2020_parser.py       2020 Rev.com
    ├── src/parsers/rev_2024_parser.py       2024 Rev.com
    ├── src/parsers/cnn_2024_parser.py       2024 CNN
    └── src/parsers/youtube_parser.py        2024 YouTube
        │
        ▼
    make normalize
    ├── src/normalizer/normalize_speakers_cspan.py          2004–2016
    ├── src/normalizer/normalize_speakers_cspan_2024.py     2024 CSPAN
    ├── src/normalizer/normalize_speakers_2020_rev.py       2020 Rev
    ├── src/normalizer/normalize_speakers_2024_rev.py       2024 Rev
    ├── src/normalizer/normalize_speakers_2024_cnn.py       2024 CNN
    ├── src/normalizer/merge_2024.py                        merge 2024 sources
    ├── src/normalizer/truecase_speeches_2004_2016.py       fix CSPAN ALL-CAPS
    ├── src/normalizer/truecase_speeches_2024.py            fix CSPAN ALL-CAPS
    └── src/build_unified_speeches.py                       → data/unified_speeches.csv
        │
        ▼
    make pronouns
    └── src/build_i_vs_we.py
        → data/pronoun_counts.csv
        → data/pronoun_counts_rolled.csv
```

---

## Repository Structure

```
.
├── Makefile
├── requirements.txt
├── notebooks/
│   ├── 01_eda.ipynb                    Initial exploratory analysis
│   ├── 02_eda.ipynb                    Extended EDA
│   ├── unified_speeches_eda.ipynb      Data quality checks
│   └── hypothesis_testing-215_cap.ipynb   Hypothesis tests (H1, H1b, H2, H2b)
├── src/
│   ├── parsers/                        One parser per transcript source
│   ├── normalizer/                     Speaker normalization + truecasing
│   ├── build_unified_speeches.py       Unify all sources into one CSV
│   └── build_i_vs_we.py               Extract pronoun counts
```

---

## Requirements

Python 3.10+

```bash
make install
```

Installs all dependencies from `requirements.txt` and downloads the spaCy `en_core_web_sm` model.

---

## Reproducing the Analysis

```bash
make parse        # Parse all raw transcripts
make normalize    # Normalize speakers, truecase, unify → data/unified_speeches.csv
make pronouns     # Extract pronoun counts → data/pronoun_counts.csv
```

Then open `notebooks/hypothesis_testing-215_cap.ipynb` to reproduce all hypothesis tests.

## Cleaning Generated Files

```bash
make clean        # Remove all generated CSVs
```

Removes all files under `data/processed/`, `data/unified_speeches.csv`, `data/pronoun_counts.csv`, and `data/pronoun_counts_rolled.csv`. Raw transcripts are not affected.

---

## Data Sources

| Year | Party | Source |
|------|-------|--------|
| 2004–2016 | Both | CSPAN |
| 2020 | Both | Rev |
| 2024 | Both | CSPAN + Rev + CNN + YouTube |

