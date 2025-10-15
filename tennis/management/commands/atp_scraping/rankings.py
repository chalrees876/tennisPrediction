
import requests
from bs4 import BeautifulSoup
from pyspark.sql import SparkSession
from w3lib.http import headers_dict_to_raw


def main():
    rankings_url = "https://www.atptour.com/en/rankings/singles?rankRange=0-5000"
    page = requests.get(rankings_url)

    rankings_soup = BeautifulSoup(page.content, 'html.parser')

    results = rankings_soup.find(class_="atp_rankings-all")

    table = results.find('table', class_="mega-table desktop-table non-live")

    upper_rows = table.find_all('tr', class_='')
    lower_rows = table.find_all('tr', class_='lower-row')

    rows = upper_rows + lower_rows

    player_rankings_list = []
    player_rankings_dict = {}

    for i, row in enumerate(rows):
        name_location = row.find(class_="name center").find('a').find('span')
        rank_location = row.find(class_="rank bold heavy tiny-cell")
        name = name_location.text.strip().replace('-', ' ')
        rank = rank_location.text.strip()
        player_rankings_list.append({
            "player": name,
            "rank": rank
        })

    spark = SparkSession.builder.appName("playerRankings").getOrCreate()

    columns=['player', 'rank']

    player_rankings = spark.createDataFrame(player_rankings_list, columns)
    player_rankings.coalesce(1).write.csv('./data/separate_data/rankings', header=True, mode='overwrite')
    return player_rankings_list

if __name__ == "__main__":
    main()