import glob
import os

import requests
import requests_cache
from selenium import webdriver
from bs4 import BeautifulSoup
from pyarrow import StructType
from pyspark.sql import SparkSession
from pyspark.sql.types import StructField, StringType, IntegerType, DoubleType
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def main():

    spark = SparkSession.builder.appName("DataFrameCreation").getOrCreate()

    csv_files = glob.glob("/Users/chrismckenzie/Downloads/tennisprediction/tennis/management/commands/atp_scraping/data/separate_data/**/*.csv", recursive=True)
    for i, file in enumerate(csv_files):
        if i == 0:
            df = spark.read.csv(file, header=True)
        else:
            temp_df = spark.read.csv(file, header=True)
            df = df.join(temp_df, on='player', how='inner')
    df.coalesce(1).write.csv('/Users/chrismckenzie/Downloads/tennisprediction/tennis/management/commands/atp_scraping/data/combined_data', header=True, mode='overwrite')

if __name__ == '__main__':
    main()