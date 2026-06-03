"""
Extract first-person pronoun counts from unified_speeches.csv.

Counting logic:
- Use regex patterns to match "I" and "we" including contracted forms.
- I patterns:  I, I'm, I've, I'll, I'd
- We patterns: we, we're, we've, we'll, we'd
- Compute rates per 1000 words for cross-speech comparison.
- Compute collective framing gap (we_rate - i_rate).
- Output both per-speech and rolled by year/party/speaker CSVs.
"""

import re
import argparse
from pathlib import Path

import pandas as pd


# --- Regex patterns (word boundary anchors prevent partial matches) ---
I_PATTERN  = re.compile(r"\bI\b|\bI'm\b|\bI've\b|\bI'll\b|\bI'd\b",  re.IGNORECASE)
WE_PATTERN = re.compile(r"\bwe\b|\bwe're\b|\bwe've\b|\bwe'll\b|\bwe'd\b", re.IGNORECASE)


def count_pronouns(text: str) -> tuple[int, int]:
    """Count I and we occurrences (including contracted forms)."""
    i_count  = len(I_PATTERN.findall(text))
    we_count = len(WE_PATTERN.findall(text))
    return i_count, we_count


def extract_counts(df: pd.DataFrame) -> pd.DataFrame:
    """Add pronoun counts and rates to dataframe."""
    df = df.copy()

    i_counts, we_counts = [], []
    for text in df["speech"]:
        i, we = count_pronouns(str(text))
        i_counts.append(i)
        we_counts.append(we)

    df["i_count"]  = i_counts
    df["we_count"] = we_counts

    # Rates per 1000 words
    df["i_rate"]  = (df["i_count"]  / df["word_count"] * 1000).round(2)
    df["we_rate"] = (df["we_count"] / df["word_count"] * 1000).round(2)

    # Collective framing gap: positive = more "we", negative = more "I"
    df["collective_gap"] = (df["we_rate"] - df["i_rate"]).round(2)

    return df


def print_summary(df: pd.DataFrame, min_words: int = 100):
    """Print analysis summary to console."""
    filtered = df[df["word_count"] >= min_words]

    print("\n" + "=" * 70)
    print("PRONOUN ANALYSIS SUMMARY")
    print("=" * 70)

    # Overall
    print(f"\nOverall (speeches >= {min_words} words, n={len(filtered)}):")
    print(f"  Avg 'I' rate:  {filtered['i_rate'].mean():.2f} per 1000 words")
    print(f"  Avg 'we' rate: {filtered['we_rate'].mean():.2f} per 1000 words")
    print(f"  Total 'I':     {filtered['i_count'].sum():,}")
    print(f"  Total 'we':    {filtered['we_count'].sum():,}")

    # By party
    print("\n--- By Party ---")
    party_stats = filtered.groupby("party").agg(
        i_rate=("i_rate", "mean"),
        we_rate=("we_rate", "mean"),
        collective_gap=("collective_gap", "mean"),
        n=("i_rate", "count")
    ).round(2)
    for party, row in party_stats.iterrows():
        print(f"  {party} (n={int(row['n'])}):")
        print(f"    'I' rate:              {row['i_rate']:.2f}/1000")
        print(f"    'we' rate:             {row['we_rate']:.2f}/1000")
        print(f"    Collective gap (we-I): {row['collective_gap']:+.2f}")

    # By year and party
    print("\n--- By Year and Party ---")
    year_party = filtered.groupby(["year", "party"]).agg(
        i_rate=("i_rate", "mean"),
        we_rate=("we_rate", "mean"),
        n=("i_rate", "count")
    ).round(2)
    print(f"  {'Year':<6} {'Party':<12} {'I rate':>8} {'We rate':>8} {'Speeches':>8}")
    print(f"  {'-'*6} {'-'*12} {'-'*8} {'-'*8} {'-'*8}")
    for (year, party), row in year_party.iterrows():
        print(f"  {year:<6} {party:<12} {row['i_rate']:>8.2f} {row['we_rate']:>8.2f} {int(row['n']):>8}")

    # Top I users
    print("\n--- Top 10 'I' Users (min 500 words) ---")
    long = df[df["word_count"] >= 500].nlargest(10, "i_rate")
    for _, row in long.iterrows():
        print(f"  {row['speaker']:<30} {row['year']} {row['party']:<12} I={row['i_rate']:.1f}/1000 ({row['word_count']} words)")

    # Top we users
    print("\n--- Top 10 'We' Users (min 500 words) ---")
    long = df[df["word_count"] >= 500].nlargest(10, "we_rate")
    for _, row in long.iterrows():
        print(f"  {row['speaker']:<30} {row['year']} {row['party']:<12} We={row['we_rate']:.1f}/1000 ({row['word_count']} words)")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/unified_speeches.csv"),
        help="Path to unified_speeches.csv"
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("data/pronoun_counts.csv"),
        help="Output CSV path (per speech)"
    )
    parser.add_argument(
        "--rolled",
        type=Path,
        default=Path("data/pronoun_counts_rolled.csv"),
        help="Output CSV path (rolled by year/party/speaker)"
    )
    parser.add_argument(
        "--min-words",
        type=int,
        default=100,
        help="Minimum word count filter for summary (default: 100)"
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Only print summary, skip CSV output"
    )
    args = parser.parse_args()

    if not args.input.exists():
        print(f"Error: Input file not found: {args.input}")
        return

    print(f"Loading speeches from {args.input}...")
    df = pd.read_csv(args.input)
    print(f"Loaded {len(df)} speeches")

    # Add a speech_id for reference
    df.insert(0, "speech_id", range(1, len(df) + 1))

    print("Computing pronoun counts...")
    df = extract_counts(df)

    if not args.summary_only:
        args.out.parent.mkdir(parents=True, exist_ok=True)

        # Per-speech output (drop full speech text)
        df.drop(columns=["speech"]).to_csv(args.out, index=False)
        print(f"Wrote per-speech counts to {args.out}")

        # Rolled by year/party/speaker
        rolled = (
            df.groupby(["year", "party", "speaker"], as_index=False)
            .agg(
                word_count=("word_count", "sum"),
                i_count=("i_count", "sum"),
                we_count=("we_count", "sum"),
                num_speeches=("speech_id", "count")
            )
        )
        # Recalculate rates from aggregated counts
        rolled["i_rate"]        = (rolled["i_count"] / rolled["word_count"] * 1000).round(2)
        rolled["we_rate"]       = (rolled["we_count"] / rolled["word_count"] * 1000).round(2)
        rolled["collective_gap"] = (rolled["we_rate"] - rolled["i_rate"]).round(2)

        rolled.to_csv(args.rolled, index=False)
        print(f"Wrote rolled counts to {args.rolled}")

    print_summary(df, min_words=args.min_words)


if __name__ == "__main__":
    main()