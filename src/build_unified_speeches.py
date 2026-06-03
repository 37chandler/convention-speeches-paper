import pandas as pd
from pathlib import Path


FILE1 = "data/processed/normalized/truecased_speeches_2004_2016.csv"
FILE2 = "data/processed/normalized/normalized_rev_2020.csv"
FILE3 = "data/processed/normalized/truecased_final_merged_2024.csv"

OUTPUT = Path("data/unified_speeches.csv")

SHARED_COLS = [
    "speaker", "party", "year", "night",
    "timestamp", "speech", "word_count",
    "source_file", "source",
]

df1 = pd.read_csv(FILE1)
df1 = df1.rename(columns={"text": "speech"})
print(f"  2004–2016: {len(df1)} rows")


df2 = pd.read_csv(FILE2)
print(f"  2020:{len(df2)} rows")

df3 = pd.read_csv(FILE3)
df3 = df3.drop(
    columns=["replaced_from_rev", "replaced_from_cnn", "appended_from_missing"],
    errors="ignore",   
)
print(f"  2024: {len(df3)} rows")

unified = pd.concat([df1, df2, df3], ignore_index=True)
unified["night"] = pd.to_numeric(unified["night"], errors="coerce")
unified = unified.sort_values(
    ["year", "party", "night", "timestamp"]
).reset_index(drop=True)


unified["word_count"] = unified["speech"].astype(str).str.split().apply(len)

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
unified.to_csv(OUTPUT, index=False)

print(f"\nSaved {len(unified)} rows → {OUTPUT}")

print("\n=== By Year × Party ===")
summary = unified.groupby(["year", "party"]).agg(
    speeches=("speech", "count"),
    total_words=("word_count", "sum"),
).reset_index()
print(summary.to_string(index=False))


print(f"Speeches: {len(unified)}")








