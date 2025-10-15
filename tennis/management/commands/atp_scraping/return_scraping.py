import requests
import requests_cache
from selenium import webdriver
from bs4 import BeautifulSoup
from pyspark.sql import SparkSession
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def main():
    url = ("https://www.atptour.com/en/stats/leaderboard?boardType=return&timeFrame=52week&surface=all&versusRank=all&formerNo1=false")

    options = webdriver.ChromeOptions()
    options.add_experimental_option("prefs", {
        "profile.managed_default_content_settings.images": 2
    })
    options.add_argument("--headless=new")

    driver = webdriver.Chrome(options=options)

    try:
        driver.get(url)

        wait = WebDriverWait(driver, 20)

        try:
            accept = wait.until(
                EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler"))
            )
            accept.click()
        except Exception:
            pass

        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.leaderboard")))

        try:
            load_more = wait.until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, ".atp_button.atp_button--secondary.loadmore")
                )
            )
            load_more.click()
            print("Button clicked successfully!")
        except Exception as e:
            print(f"No/failed 'Load more' click (continuing): {e}")

        html_content = driver.page_source

    finally:
        driver.quit()
    stats_soup = BeautifulSoup(html_content, 'html.parser')

    leaderboard_container = stats_soup.find('div', class_='leaderboard')

    headers = leaderboard_container.find_all('th')

    header_list = []

    for header in headers:
        header_loc = header.find('div', class_='label')
        if header_loc is not None:
            header_list.append(header_loc.text.strip())

    rows = leaderboard_container.find('tbody').find_all('tr')
    player_stats_list = []

    for row in rows:
        columns = row.find_all('td')
        print(columns)
        for i, column in enumerate(columns):
            if i == 1:
                name = column.find('div', class_='name').find('a').text.strip().replace('-', ' ')
            elif i == 2:
                serve_rating = column.text.strip()
            elif i == 3:
                fsp = column.text.strip()
            elif i == 4:
                fspw = column.text.strip()
            elif i == 5:
                sspw = column.text.strip()
            elif i == 6:
                sgwp = column.text.strip()
            else:
                continue
        player_stats_dict = dict(zip(header_list, [name, serve_rating, fsp, fspw, sspw, sgwp]))
        player_stats_list.append(player_stats_dict)

    spark = SparkSession.builder.appName("playerStats").getOrCreate()
    player_stats = spark.createDataFrame(player_stats_list)
    player_stats.show()

    player_stats.coalesce(1).write.csv('./data/separate_data/return_data',
                                  header=True, mode='overwrite')
    print(player_stats_list)
    return player_stats_list

if __name__ == "__main__":
    main()