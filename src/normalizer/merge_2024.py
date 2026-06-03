import pandas as pd

REV_FILE = "data/processed/normalized/normalized_rev_2024.csv"
CNN_FILE = "data/processed/normalized/normalized_cnn_2024.csv"
CSPAN_FILE = "data/processed/normalized/normalized_cspan_2024.csv"
MISSING_FILE = "data/processed/parsed/rnc_night_1_missing_speakers.csv"
OUTPUT_FILE = "data/processed/normalized/normalized_final_merged_2024.csv"

KEY_COLS = ["speaker", "party", "year", "night"]

CNN_SWAPS = {
    ("Josh Shapiro",           "Democratic", 2024, 3),
    ("Andy Beshear",           "Democratic", 2024, 1),
    ("Catherine Cortez Masto", "Democratic", 2024, 3),
    ("Trent Conaway",          "Republican", 2024, 3),
    ("Tony Goldwyn",           "Democratic", 2024, 1),
    ("Ana Navarro",            "Democratic", 2024, 2),
    ("J.B. Pritzker",          "Democratic", 2024, 2),
    ("Amy Klobuchar",          "Democratic", 2024, 3),
    ("Benjamin Ingman",        "Democratic", 2024, 3),
    ("Leon Panetta",           "Democratic", 2024, 4),
    ("Maxwell Frost",          "Democratic", 2024, 4),
    ("Madeline Brame",         "Republican", 2024, 2),
    ("William Pekrul",         "Republican", 2024, 3),
    ("Jamie Raskin",           "Democratic", 2024, 1),
    ("Jasmine Crockett",       "Democratic", 2024, 1),
    ("Steve Kerr",             "Democratic", 2024, 1),
    ("Amanda Gorman",          "Democratic", 2024, 3),
    ("Annette Albright",       "Republican", 2024, 4),
}


def normalize_key_cols(df):
    df["speaker"] = df["speaker"].astype(str).str.strip()
    df["party"] = df["party"].astype(str).str.strip()
    df["year"] = df["year"].astype(int)
    df["night"] = df["night"].astype(int)
    return df


def ensure_speech_column(df):
    if "text" in df.columns and "speech" not in df.columns:
        df = df.rename(columns={"text": "speech"})
    return df


def replace_from_source(base_df, source_df, source_flag_col, allowed_keys=None):
    """
    Replace speech/source/source_file/word_count in base_df from source_df.
    Keeps base_df metadata like timestamp, party, year, night.
    If allowed_keys is provided, only those exact keys are replaced.
    """
    for key, src_group in source_df.groupby(KEY_COLS):
        if allowed_keys is not None and key not in allowed_keys:
            continue

        base_idx = base_df.index[
            (base_df["speaker"] == key[0]) &
            (base_df["party"] == key[1]) &
            (base_df["year"] == key[2]) &
            (base_df["night"] == key[3])
        ].tolist()

        if len(base_idx) == 0:
            continue

        # Normal one-row match
        if len(base_idx) == 1 and len(src_group) >= 1:
            src_row = src_group.iloc[0]
            idx = base_idx[0]

            base_df.at[idx, "speech"] = src_row["speech"]
            base_df.at[idx, "word_count"] = len(str(src_row["speech"]).split())
            base_df.at[idx, "source"] = src_row["source"]
            base_df.at[idx, "source_file"] = src_row["source_file"]
            base_df.at[idx, source_flag_col] = 1

        # Special case: Donald Trump Jr. -> replace second row only
        elif key == ("Donald Trump Jr.", "Republican", 2024, 3) and len(base_idx) >= 2 and len(src_group) >= 1:
            src_row = src_group.iloc[0]
            subset = base_df.loc[base_idx].copy().sort_values("timestamp")
            idx = subset.index.tolist()[1]

            base_df.at[idx, "speech"] = src_row["speech"]
            base_df.at[idx, "word_count"] = len(str(src_row["speech"]).split())
            base_df.at[idx, "source"] = src_row["source"]
            base_df.at[idx, "source_file"] = src_row["source_file"]
            base_df.at[idx, source_flag_col] = 1

        else:
            continue

    return base_df


def main():
    cspan = pd.read_csv(CSPAN_FILE)
    rev = pd.read_csv(REV_FILE)
    cnn = pd.read_csv(CNN_FILE)
    missing = pd.read_csv(MISSING_FILE)

    cspan = normalize_key_cols(cspan)
    rev = normalize_key_cols(ensure_speech_column(rev))
    cnn = normalize_key_cols(ensure_speech_column(cnn))
    missing = normalize_key_cols(ensure_speech_column(missing))

    # tracking columns
    if "replaced_from_rev" not in cspan.columns:
        cspan["replaced_from_rev"] = 0
    if "replaced_from_cnn" not in cspan.columns:
        cspan["replaced_from_cnn"] = 0
    if "appended_from_missing" not in cspan.columns:
        cspan["appended_from_missing"] = 0

    # 1. Replace from REV first
    cspan = replace_from_source(
        base_df=cspan,
        source_df=rev,
        source_flag_col="replaced_from_rev",
        allowed_keys=None
    )

    # 2. Replace selected rows from CNN
    cspan = replace_from_source(
        base_df=cspan,
        source_df=cnn,
        source_flag_col="replaced_from_cnn",
        allowed_keys=CNN_SWAPS
    )

    # 3. Append missing rows only if exact key is not already present
    existing_keys = set(
        tuple(row[col] for col in KEY_COLS)
        for _, row in cspan.iterrows()
    )

    rows_to_append = []
    for _, row in missing.iterrows():
        key = tuple(row[col] for col in KEY_COLS)

        if key not in existing_keys:
            new_row = row.to_dict()
            new_row["replaced_from_rev"] = 0
            new_row["replaced_from_cnn"] = 0
            new_row["appended_from_missing"] = 1
            rows_to_append.append(new_row)

    if rows_to_append:
        missing_df = pd.DataFrame(rows_to_append)

        for col in cspan.columns:
            if col not in missing_df.columns:
                missing_df[col] = None

        missing_df = missing_df[cspan.columns]
        final_df = pd.concat([cspan, missing_df], ignore_index=True)
    else:
        final_df = cspan.copy()

    # 4. Clean whitespace but PRESERVE CASE
    final_df["speech"] = final_df["speech"].astype(str).str.strip()

    # 5. Recompute word_count after uppercasing
    final_df["word_count"] = final_df["speech"].apply(lambda x: len(str(x).split()))

    # 6. Uppercase source for consistency
    final_df["source"] = final_df["source"].astype(str).str.upper().str.strip()

    # 7. Sort final output
    final_df = final_df.sort_values(
        by=["party", "year", "night", "timestamp", "speaker"],
        na_position="last"
    ).reset_index(drop=True)

    final_df.to_csv(OUTPUT_FILE, index=False)

    print(f"Saved merged file to: {OUTPUT_FILE}")
    print(f"Rows replaced from Rev: {int(final_df['replaced_from_rev'].sum())}")
    print(f"Rows replaced from CNN: {int(final_df['replaced_from_cnn'].sum())}")
    print(f"Rows appended from missing file: {int(final_df['appended_from_missing'].sum())}")


if __name__ == "__main__":
    main()