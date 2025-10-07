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
from pyspark.sql import functions as F

spark = (SparkSession.builder
         .appName("pandas-to-pyspark")
         .config("spark.sql.shuffle.partitions", "16")
         .getOrCreate()
         )

points_df = spark.read.csv("../data/charting-m-points-2020s.csv", header=True)

matches = points_df.select('match_id').distinct()

matches = matches.select(
    'match_id',
    F.split('match_id', '-').getItem(0).alias('date'),
    F.split('match_id', '-').getItem(1).alias('gender'),
    F.split('match_id', '-').getItem(2).alias('tournament'),
    F.split('match_id', '-').getItem(3).alias('round'),
    F.split('match_id', '-').getItem(4).alias('player_1'),
    F.split('match_id', '-').getItem(5).alias('player_2'),
    ).withColumns({
        'tournament': F.translate('tournament', '_', ' '),
        'player_1': F.translate('player_1', '_', ' '),
        'player_2': F.translate('player_2', '_', ' '),
    })

points_df = points_df.withColumns({
    '1st': F.translate(points_df['1st'], 'c', ''),
    '2nd': F.translate(points_df['2nd'], 'c', '')
})

points_df = points_df.withColumn('1st serve fault', points_df['2nd'].isNotNull())
points_df = points_df.withColumn('2nd serve fault', F.substring(points_df['2nd'], 2, 1).isin(list(error_code.keys()))).fillna(False)
test = points_df.groupBy(
        'match_id', 'Svr').agg(
        F.round((100 * F.sum((~F.col('1st serve fault')).cast('integer')) / F.count('1st'))).alias("first serve percent"),
        F.round((100 * F.sum((~F.col('2nd serve fault')).cast('integer')) / F.count('2nd serve fault'))).alias("second serve percent"),
        F.sum((F.col('2nd serve fault')).cast('integer')).alias("double faults")
    )
test = test.groupBy('match_id').agg(
    F.first(F.when(F.col('Svr')==1, F.col('first serve percent')), ignorenulls=True).alias('p1 fsp'),
    F.first(F.when(F.col('Svr')==1, F.col('second serve percent')), ignorenulls=True).alias('p1 ssp'),
    F.first(F.when(F.col('Svr')==1, F.col('double faults')), ignorenulls=True).alias('p1 df'),
    F.first(F.when(F.col('Svr')==2, F.col('first serve percent')), ignorenulls=True).alias('p2 fsp'),
    F.first(F.when(F.col('Svr')==2, F.col('second serve percent')), ignorenulls=True).alias('p2 fsp'),
    F.first(F.when(F.col('Svr')==2, F.col('double faults')), ignorenulls=True).alias('p2 fsp')
)
test.sort('match_id').show(truncate=0)

matches = matches.join(test, on='match_id', how='left' )
matches.show()

"""matches = matches.withColumn('p1 fsp',
    points_df.where(F.col('Svr')==1).groupBy(
    'match_id').agg(
    (100 * F.sum((~F.col('1st serve fault')).cast('integer')) / F.max(F.col('Pt'))).alias('fsp')
    ).select(points_df['fsp']))"""
"""Lets look at one match data and get first serve percentages and second serve percentages for that match
for match in matches.collect():
    single_match_id = match['match_id']
    points_df = df.where(df.match_id == single_match_id)  # create a dataframe using only the data from that match id
    points_df = points_df.withColumn('1st serve fault', points_df['2nd'].isNotNull())  # add first serve fault column
    points_df = points_df.withColumn("1st", translate('1st', 'c', ''))  # remove lets
    points_df = points_df.withColumn("2nd", translate('2nd', 'c', ''))  # remove lets
    points_df = points_df.select("*", substring(points_df['2nd'], 2, 1).alias("ss error code"))
    points_df = points_df.withColumn('2nd serve fault', points_df['ss error code'].isin(list(error_code.keys())))
    points_df = points_df.withColumn("DoubleFault", points_df['2nd serve fault'])
    points_df = points_df.drop("ss error code")

    match_df = points_df.select(
        split('match_id', '-').getItem(0).alias('date'),
        split('match_id', '-').getItem(1).alias('gender'),
        split('match_id', '-').getItem(2).alias('tournament'),
        split('match_id', '-').getItem(3).alias('round'),
        split('match_id', '-').getItem(4).alias('player_1'),
        split('match_id', '-').getItem(5).alias('player_2'),
    )


    def get_serve_data(player_num, df):
        fsp = round(lit(100 * (df.filter((df['Svr'] == player_num) & (~df['1st serve fault'])).count() / (
            df.filter(df['Svr'] == player_num).count()))))
        ssp = round(lit(100 * (df.filter(
            (df['Svr'] == player_num) & (df['1st serve fault']) & (~df['2nd serve fault'])).count() / (
                                   df.filter((df['Svr'] == player_num) & (df['1st serve fault']))).count())))
        double_faults = lit(
            df.filter((df['Svr'] == player_num) & (df['1st serve fault']) & (df['2nd serve fault'])).count())
        return fsp, ssp, double_faults


    p1_fsp, p1_ssp, p1_df = get_serve_data(1, points_df)
    p2_fsp, p2_ssp, p2_df = get_serve_data(2, points_df)

    match_df = match_df.distinct()
    match_df = match_df.withColumns(
        {'p1fsp': p1_fsp,
         'p1ssp': p1_ssp,
         'p1df': p1_df,
         'p2fsp': p2_fsp,
         'p2ssp': p2_ssp,
         'p2df': p2_df})

    match_df = match_df.withColumn('tournament', translate('tournament', '_', ' '))
    match_df = match_df.withColumn('player_1', translate('player_1', '_', ' '))
    match_df = match_df.withColumn('player_2', translate('player_2', '_', ' '))

end_time = time.time()
exec_time = end_time - start_time
print("execution time:", exec_time)"""

