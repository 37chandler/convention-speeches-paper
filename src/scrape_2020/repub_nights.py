from pathlib import Path
import time
from selenium import webdriver
from selenium.webdriver.common.by import By

OUTPUT_DIR = Path("data/raw/cspan/2020/Republican")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

pages = {
    "rnc_2020_night_1.txt": "https://www.c-span.org/program/republican-national-convention/republican-national-convention-day-1/551576",
    "rnc_2020_night_2.txt": "https://www.c-span.org/program/public-affairs-event/republican-national-convention-day-2/551577",
    "rnc_2020_night_3.txt": "https://www.c-span.org/program/public-affairs-event/republican-national-convention-day-3/551578",
    "rnc_2020_night_4.txt": "https://www.c-span.org/program/republican-national-convention/republican-national-convention-day-4/551579",
}

driver = webdriver.Chrome()

for file_name, url in pages.items():
    output_path = OUTPUT_DIR / file_name

    # Skip if already saved with content
    if output_path.exists() and output_path.stat().st_size > 1000:
        print(f"SKIP {file_name} — already saved ({output_path.stat().st_size:,} chars)")
        continue

    print(f"\nOpening {file_name}...")
    driver.get(url)
    time.sleep(15)

    try:
        transcript = driver.find_element(By.ID, "video-transcript-table")
        transcript_text = transcript.text

        if len(transcript_text) < 1000:
            print(f"  WARNING: too short ({len(transcript_text)} chars) — skipping save")
            print(f"  C-SPAN may be rate limiting. Wait a few minutes and retry.")
            continue

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(transcript_text)

        print(f"  Saved → {output_path} ({len(transcript_text):,} chars)")

    except Exception as e:
        print(f"  No transcript found: {e}")

    time.sleep(10)

driver.quit()
print("\nDone.")