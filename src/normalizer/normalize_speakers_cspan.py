import csv
from pathlib import Path
from collections import defaultdict

# paths
parsed_path = Path("data/processed/parsed/parsed_cspan_2004_2016.csv")
aliases_path = Path("data/reference/aliases_2004_2016_unified.csv")
output_path = Path("data/processed/normalized/normalized_speeches_2004_2016.csv")


# load aliases
aliases = {}
with open(aliases_path, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        aliases[row["alias"].strip()] = row["canonical"].strip()


# normalize
speeches = []
with open(parsed_path, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        name = row["speaker"].strip()

        # apply alias
        if name in aliases:
            if aliases[name] == "EXCLUDE":
                continue
            row["speaker"] = aliases[name]

        speeches.append(row)


# aggregate by (speaker, party, year, night)
groups = defaultdict(list)
for row in speeches:
    key = (row["speaker"], row["party"], row["year"], row["night"])
    groups[key].append(row)


final_rows = []
for group in groups.values():
    if len(group) == 1:
        final_rows.append(group[0])
    else:
        group.sort(key=lambda r: r["timestamp"])
        merged = group[0].copy()
        merged["text"] = " ".join(r["text"] for r in group)
        merged["word_count"] = str(sum(int(r["word_count"]) for r in group))
        final_rows.append(merged)


# sort nicely
final_rows.sort(key=lambda r: (
    int(r["year"]),
    r["party"],
    int(r["night"]),
    r["speaker"]
))


# write output
output_path.parent.mkdir(parents=True, exist_ok=True)
with open(output_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=final_rows[0].keys())
    writer.writeheader()
    writer.writerows(final_rows)


print(f"Done. Final rows: {len(final_rows)}")