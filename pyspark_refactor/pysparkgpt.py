# pyspark_testing.py
# Force JDK 17 for this process (before importing pyspark)
import os
import subprocess
import time

serve_code = {"4": "W",
         "5": "B",
         "6": "T",
        "u": "Underhand"}

return_depth_code = {
    "7": "inside service line",
    "8": "behind service line",
    "9": "deep",
    "0": "unknown"
}

shot_code = {"f": "forehand",
        "b": "backhand",
        "s": "backhand slice",
        "r": "forehand slice",
        "v": "forehand volley",
        "z": "backhand volley",
        "o": "overhead",
        "p": "backhand overhead smash",
        "u": "forehand drop shot",
        "y": "backhand drop shot",
        "l": "forehand lob",
        "m": "backhand lob",
        "h": "forehand half-volley",
        "i": "backhand half-volley",
        "j": "forehand swinging volley",
        "k": "backhand swinging volley",
        "t": "trick shot",
        "q": "unknown"}

shot_direction_code = {"1": "deuce side",
                  "2": "down middle",
                  "3": "ad side"}

point_end_code = {"@": "unforced error",
             "#": "forced error",
             "*": "winner"}

error_code = {"n": "net",
         "w": "wide",
         "d": "deep",
         "x": "wide and deep",
         "!": "shank",
         "e": "unknown"}

optional_code = {"+": "approach shot",
            "-": "net",
            "=": "baseline",
            "^": "drop volley"}


if "JAVA_HOME" not in os.environ or "17" not in os.environ["JAVA_HOME"]:
    os.environ["JAVA_HOME"] = subprocess.check_output(
        ["/usr/libexec/java_home", "-v", "17"]
    ).decode().strip()

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, split, translate, substring, when, count, sum as ssum, first, round as sround
)
from pyspark.sql.types import StructType, StructField, StringType, IntegerType


spark = (
    SparkSession.builder
    .appName("tennis-serve-stats")
    # tune this to roughly 2–3× your total core count
    .config("spark.sql.shuffle.partitions", "64")
    .getOrCreate()
)

# ---- Adjust schema to your file; explicit schema avoids slow inference ----
schema = StructType([
    StructField("match_id", StringType(), True),
    StructField("Pt", StringType(), True),
    StructField("Svr", IntegerType(), True),  # 1 or 2
    StructField("1st", StringType(), True),
    StructField("2nd", StringType(), True),
    # ... add any other columns you actually need later; extras are fine to omit
])

csv_path = "../data/charting-m-points-2020s.csv"

df = (
    spark.read
    .option("header", "true")
    .schema(schema)         # comment this out if you prefer inference
    .csv(csv_path)
)

# ---- One-time cleanup & feature flags (vectorized, not per-match) ----
# Remove 'c' (lets) from serve codes, derive fault flags
clean = (
    df
    .withColumn("first_clean", translate(col("1st"), "c", ""))   # not used in counts below, but kept if needed
    .withColumn("second_clean", translate(col("2nd"), "c", ""))
    .withColumn("first_fault", col("2nd").isNotNull())
    # grab 2nd-serve error-code (2nd char) and decide if it's a fault
    .withColumn("ss_err", substring(col("second_clean"), 2, 1))
)

# Error codes indicating a second-serve fault (from your mapping)
error_codes = ["n", "w", "d", "x", "!", "e"]

clean = clean.withColumn(
    "second_fault",
    col("ss_err").isin(error_codes)
)

# Split metadata from match_id once
meta = (
    clean
    .select("match_id")
    .distinct()
    .withColumn("date",       split(col("match_id"), "-").getItem(0))
    .withColumn("gender",     split(col("match_id"), "-").getItem(1))
    .withColumn("tournament", split(col("match_id"), "-").getItem(2))
    .withColumn("round",      split(col("match_id"), "-").getItem(3))
    .withColumn("player_1",   split(col("match_id"), "-").getItem(4))
    .withColumn("player_2",   split(col("match_id"), "-").getItem(5))
    .withColumn("tournament", translate(col("tournament"), "_", " "))
    .withColumn("player_1",   translate(col("player_1"), "_", " "))
    .withColumn("player_2",   translate(col("player_2"), "_", " "))
)

# (Helps distribution by the group keys we’ll use)
points = clean.repartition("match_id", "Svr")

# ---- Single aggregation over all matches & both servers ----
agg = (
    points
    .groupBy("match_id", "Svr")
    .agg(
        count("*").alias("total_serves"),
        ssum(when(~col("first_fault"), 1).otherwise(0)).alias("first_in"),
        ssum(when(col("first_fault"), 1).otherwise(0)).alias("first_faults"),
        ssum(when(col("first_fault") & ~col("second_fault"), 1).otherwise(0)).alias("second_in"),
        ssum(when(col("first_fault") &  col("second_fault"), 1).otherwise(0)).alias("double_faults")
    )
    # derive percentages safely (avoid div-by-zero)
    .withColumn(
        "fsp",
        sround(when(col("total_serves") > 0, col("first_in") / col("total_serves") * 100).otherwise(None), 1)
    )
    .withColumn(
        "ssp",
        sround(when(col("first_faults") > 0, col("second_in") / col("first_faults") * 100).otherwise(None), 1)
    )
)

# ---- Convert (match_id, Svr) rows into wide p1*/p2* columns per match ----
wide = (
    agg
    .groupBy("match_id")
    .agg(
        first(when(col("Svr") == 1, col("fsp")),           ignorenulls=True).alias("p1fsp"),
        first(when(col("Svr") == 1, col("ssp")),           ignorenulls=True).alias("p1ssp"),
        first(when(col("Svr") == 1, col("double_faults")), ignorenulls=True).alias("p1df"),
        first(when(col("Svr") == 2, col("fsp")),           ignorenulls=True).alias("p2fsp"),
        first(when(col("Svr") == 2, col("ssp")),           ignorenulls=True).alias("p2ssp"),
        first(when(col("Svr") == 2, col("double_faults")), ignorenulls=True).alias("p2df"),
    )
)

# ---- Join back match metadata and produce final per-match frame ----
result = (
    meta.join(wide, on="match_id", how="left")
    .select(
        "date", "gender", "tournament", "round", "player_1", "player_2",
        "p1fsp", "p1ssp", "p1df", "p2fsp", "p2ssp", "p2df"
    )
)

# Optionally materialize to Parquet/Delta for future fast reads:
# result.write.mode("overwrite").parquet("../data/serve_stats.parquet")

# Trigger execution
print(f"Matches computed: {result.count()}")
result.show(10, truncate=False)