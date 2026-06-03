from pathlib import Path
import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

OUTPUT_DIR = Path("data/raw/cspan/2020/Republican")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

driver = webdriver.Chrome()

pages = {
    "dnc_2020_night_1.txt": "https://www.c-span.org/program/public-affairs-event/democratic-national-convention-day-1/550966",
    "dnc_2020_night_2.txt": "https://www.c-span.org/program/democratic-national-convention/democratic-national-convention-day-2/550967",
    "dnc_2020_night_3.txt": "https://www.c-span.org/program/public-affairs-event/democratic-national-convention-day-3/550968",
    "dnc_2020_night_4.txt": "https://www.c-span.org/program/public-affairs-event/democratic-national-convention-day-4/550969",
}

for file_name, url in pages.items():
    print(f"\nOpening {file_name}...")

    driver.get(url)
    time.sleep(15)

    try:
        transcript = driver.find_element(By.ID, "video-transcript-table")
        transcript_text = transcript.text

        with open(file_name, "w", encoding="utf-8") as f:
            f.write(transcript_text)

        print(f" Saved {file_name} ({len(transcript_text)} chars)")

    except:
        print(f" No transcript found for {file_name}")

driver.quit()