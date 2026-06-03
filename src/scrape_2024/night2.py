from selenium import webdriver
from selenium.webdriver.common.by import By
import time

driver = webdriver.Chrome()
driver.get("https://www.c-span.org/program/campaign-2024/republican-national-convention-day-2/644518")

# Wait for transcript to load
time.sleep(5)

# Grab transcript text
transcript = driver.find_element(By.ID, "video-transcript-table")
transcript_text = transcript.text

# Save to file
with open("rnc_2024_night_2.txt", "w") as f:
    f.write(transcript_text)

print(f"Done! Saved {len(transcript_text)} characters to transcript.txt")

driver.quit()