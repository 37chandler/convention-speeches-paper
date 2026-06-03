from selenium import webdriver
from selenium.webdriver.common.by import By
import time

driver = webdriver.Chrome()

pages = {
    "dnc_2024_night_1.txt": "https://www.c-span.org/program/campaign-2024/democratic-national-convention-day-1/647458",
    "dnc_2024_night_2.txt": "https://www.c-span.org/program/campaign-2024/democratic-national-convention-day-2/647459",
    "dnc_2024_night_3.txt": "https://www.c-span.org/program/campaign-2024/democratic-national-convention-day-3/647460",
    "dnc_2024_night_4.txt": "https://www.c-span.org/program/campaign-2024/democratic-national-convention-day-4/647461",
}

for file_name, url in pages.items():
    print(f"\nOpening {file_name}...")

    driver.get(url)
    time.sleep(5)

    try:
        transcript = driver.find_element(By.ID, "video-transcript-table")
        transcript_text = transcript.text

        with open(file_name, "w", encoding="utf-8") as f:
            f.write(transcript_text)

        print(f" Saved {file_name} ({len(transcript_text)} chars)")

    except:
        print(f" No transcript found for {file_name}")

driver.quit()