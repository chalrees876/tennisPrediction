from pprint import pprint

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By


def get_men_player_data():
    # Set up Chrome options
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in background
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-images")  # Block images for faster loading
    chrome_options.add_experimental_option("prefs", {
        "profile.managed_default_content_settings.images": 2,  # Disable images
    })

    # Initialize driver
    driver = webdriver.Chrome(options=chrome_options)

    driver.get("https://www.tennisabstract.com/cgi-bin/leaders.cgi")

    table = driver.find_element(By.ID, "matches")
    print(table)

    header_data = table.find_elements(By.TAG_NAME, "th")
    headers = [header.text for header in header_data if header.text.strip()]
    print(headers)


    rows = table.find_element(By.TAG_NAME, "tbody").find_elements(By.TAG_NAME, "tr")
    total_data = []
    for row in rows:
        cell_data = row.find_elements(By.TAG_NAME, "td")
        cell_text = [cell.text for cell in cell_data if cell.text.strip()]
        cell_dict = dict(zip(headers, cell_text))
        total_data.append(cell_dict)
    driver.close()
    return total_data

pprint(get_men_player_data())