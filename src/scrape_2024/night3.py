from selenium import webdriver
from selenium.webdriver.common.by import By
import time

driver = webdriver.Chrome()

driver.get("https://www.c-span.org/program/campaign-2024/republican-national-convention-day-3/644519")


time.sleep(6)

# Grab transcript text
transcript = driver.find_element(By.ID, "video-transcript-table")
transcript_text = transcript.text


with open("rnc_2024_night_3.txt", "w") as f:
    f.write(transcript_text)

print(f"Done! Saved {len(transcript_text)} characters to transcript.txt")

driver.quit()