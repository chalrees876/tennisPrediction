# pyspark_testing.py
# Force JDK 17 for this process (before importing pyspark)
import os
import subprocess

if "JAVA_HOME" not in os.environ or "17" not in os.environ["JAVA_HOME"]:
    os.environ["JAVA_HOME"] = subprocess.check_output(
        ["/usr/libexec/java_home", "-v", "17"]
    ).decode().strip()

from pyspark.sql import SparkSession
from pyspark.sql.functions import *

spark = (SparkSession.builder
         .appName("pandas-to-pyspark")
         .config("spark.sql.shuffle.partitions", "8")
         .getOrCreate()
         )

df = spark.read.csv("../data/charting-m-points-2020s.csv", header=True)

matches = df.select('match_id').distinct()

split_df = matches.select(
    split('match_id', '-').getItem(0).alias('date'),
    split('match_id', '-').getItem(1).alias('gender'),
    split('match_id', '-').getItem(2).alias('tournament'),
    split('match_id', '-').getItem(3).alias('round'),
    split('match_id', '-').getItem(4).alias('player_1'),
    split('match_id', '-').getItem(5).alias('player_2'),
)

print(split_df.columns)

for c in split_df.columns:
    split_df = split_df.withColumn(c, regexp_replace(c, "_", " "))

split_df.show()







