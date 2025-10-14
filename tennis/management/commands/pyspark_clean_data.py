# pyspark_clean_data.py
# Force JDK 17 for this process (before importing pyspark)
import glob
import os
import subprocess
import time

import django
from pyspark.sql.functions import lit

from pyspark.sql.types import StringType, IntegerType, StructField, BooleanType, StructType


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

from pyspark.sql import SparkSession, Window
from pyspark.sql import functions as F

spark = (SparkSession.builder
         .appName("pandas-to-pyspark")
         .config("spark.sql.shuffle.partitions", "16")
         .getOrCreate()
         )

schema = StructType([
    StructField('match_id', StringType(), True),
    StructField('Pt', IntegerType(), True),
    StructField('Set1', IntegerType(), True),
    StructField('Set2', IntegerType(), True),
    StructField('Gm1', IntegerType(), True),
    StructField('Gm2', IntegerType(), True),
    StructField('Pts', StringType(), True),
    StructField('Gm#', IntegerType(), True),
    StructField('TbSet', BooleanType(), True),
    StructField('Svr', IntegerType(), True),
    StructField('1st', StringType(), True),
    StructField('2nd', StringType(), True),
    StructField('Notes', StringType(), True),
    StructField('PtWinner', IntegerType(), True),
])

csv_files = glob.glob("/Users/chrismckenzie/Downloads/tennisprediction/tennis/data/raw_data/*.csv")
points_df = spark.read.csv(csv_files, header=True, schema=schema)
matches = points_df.select('match_id').distinct()
windowSpec = Window.partitionBy('match_id').orderBy('Pt')
points_df = points_df.withColumns({
    'P1gamesrank': lit(0),
    'P1games': lit(0),
    'P2games':lit(0),
    'P1sets':lit(0),
    'P2sets': lit(0)})

points_df = (points_df.withColumn("p1_fs_point",
                F.when(
                    ((F.col('Svr') == 1)  & (F.col('2nd').isNull())),
                    True
                    ).otherwise(False)
                ).withColumn("p2_fs_point",
                F.when(
                    ((F.col('Svr') == 2) & (F.col('2nd').isNull())),
                    True
                    ).otherwise(False)
                ).withColumn("p1_ss_point",
                F.when(
                    ((F.col('Svr') == 1) & (F.col('2nd').isNotNull())),
                    True
                    ).otherwise(False)
                ).withColumn("p2_ss_point",
                F.when(
                    ((F.col('Svr') == 2) & (F.col('2nd').isNotNull())),
                    True
                    ).otherwise(False)
                ).withColumn("p1_fsr_point",
                F.when(
                    ((F.col('Svr') == 2) & (F.col('2nd').isNull())),
                    True
                    ).otherwise(False)
                ).withColumn("p2_fsr_point",
                F.when(
                    ((F.col('Svr') == 1) & (F.col('2nd').isNull())),
                    True
                    ).otherwise(False)
                ).withColumn("p1_ssr_point",
                F.when(
                    ((F.col('Svr') == 2) & (F.col('2nd').isNotNull())),
                    True
                    ).otherwise(False)
                ).withColumn("p2_ssr_point",
                F.when(
                    ((F.col('Svr') == 1) & (F.col('2nd').isNotNull())),
                    True
                    ).otherwise(False)
                )
             )

points_df = (points_df.withColumn("p1_fsw_point",
                F.when(
                    ((F.col('Svr') == 1) & (F.col('PtWinner') == 1) & F.col('2nd').isNull()),
                True).otherwise(False)
                ).withColumn("p2_fsw_point",
                F.when(
                    ((F.col('Svr') == 2) & (F.col('PtWinner') == 2) & F.col('2nd').isNull()),
                True).otherwise(False)
                ).withColumn("p1_ssw_point",
                F.when(
                    ((F.col('Svr') == 1) & (F.col('PtWinner') == 1) & F.col('2nd').isNotNull()),
                True).otherwise(False)
                )
                .withColumn("p2_ssw_point",
                F.when(
                    ((F.col('Svr') == 2) & (F.col('PtWinner') == 2) & F.col('2nd').isNotNull()),
                True).otherwise(False)
                ).withColumn("p1_fsrw_point",
                F.when(
                    ((F.col('Svr') == 2) & (F.col('PtWinner') == 1) & F.col('2nd').isNull()),
                    True).otherwise(False)
                ).withColumn("p2_fsrw_point",
                F.when(
                    ((F.col('Svr') == 1) & (F.col('PtWinner') == 2) & F.col('2nd').isNull()),
                    True).otherwise(False)
                ).withColumn("p1_ssrw_point",
                F.when(
                    ((F.col('Svr') == 2) & (F.col('PtWinner') == 1) & F.col('2nd').isNotNull()),
                    True).otherwise(False)
                ).withColumn("p2_ssrw_point",
                F.when(
                    ((F.col('Svr') == 1) & (F.col('PtWinner') == 2) & F.col('2nd').isNotNull()),
                    True).otherwise(False)
                )
            )

points_df.show()

match_stats_df = points_df.orderBy('Pt').groupby('match_id').agg(
    (F.sum(
        F.col('p1_fsw_point').cast('integer')
    ) /
    F.sum(F.col('p1_fs_point').cast('integer')
          )).alias('p1_fswp'),
    (F.sum(
        F.col('p2_fsw_point').cast('integer')
    ) /
    F.sum(F.col('p2_fs_point').cast('integer')
          )).alias('p2_fswp'),
    (F.sum(
            F.col('p1_ssw_point').cast('integer')
        ) /
        F.sum(F.col('p1_ss_point').cast('integer')
              )).alias('p1_sswp'),
    (F.sum(
            F.col('p2_ssw_point').cast('integer')
        ) /
        F.sum(F.col('p2_ss_point').cast('integer')
              )).alias('p2_sswp'),
    (F.sum(
            (F.col('p1_fsrw_point')).cast('integer')
        ) /
        F.sum(F.col('p1_fsr_point').cast('integer')
              )).alias('p1_fsrwp'),
    (F.sum(
            (F.col('p2_fsrw_point')).cast('integer')
        ) /
        F.sum(F.col('p2_fsr_point').cast('integer')
              )).alias('p2_fsrwp'),
    (F.sum(
            (F.col('p1_ssrw_point')).cast('integer')
        ) /
        F.sum(F.col('p1_ssr_point').cast('integer')
              )).alias('p1_ssrwp'),
    (F.sum(
            (F.col('p2_ssrw_point')).cast('integer')
        ) /
        F.sum(F.col('p2_ssr_point').cast('integer')
              )).alias('p2_ssrwp'),
)

match_stats_df.show(truncate=False)

points_df = points_df.withColumn('P1games', F.sum(F.col('P1gamesrank')).over(windowSpec))

points_df = (points_df
             .withColumn('P1games',
                F.when(
                    (F.lead(F.col('Gm1'), 1, 0).over(windowSpec) == 0) &
                    (F.lag(F.col('Gm1'), 1, 0).over(windowSpec) != 0) &
                    (F.col('PtWinner') == 1),
                    F.col('Gm1') + 1
                    ).otherwise(
                    F.col('Gm1')
                    )
                )
             .withColumn('P2games',
                 F.when(
                     (F.lead(F.col('Gm2'), 1, 0).over(windowSpec) == 0) &
                     (F.lag(F.col('Gm2'), 1, 0).over(windowSpec) != 0) &
                     (F.col('PtWinner') == 2),
                     F.col('Gm2') + 1
                    ).otherwise(
                     F.col('Gm2')
                        )
                    )
                )

points_df = points_df.withColumn('tempSet1Score', F.when(
    ((F.col('Set1') + F.col('Set2')) == 0), F.concat(F.col('P1games').cast("string"), lit("-"), F.col('P2games').cast("string")))
)
points_df = points_df.withColumn('tempSet2Score', F.when(
    ((F.col('Set1') + F.col('Set2')) == 1), F.concat(F.col('P1games').cast("string"), lit("-"), F.col('P2games').cast("string")))
)
points_df = points_df.withColumn('tempSet3Score', F.when(
    ((F.col('Set1') + F.col('Set2')) == 2), F.concat(F.col('P1games').cast("string"), lit("-"), F.col('P2games').cast("string")))
)
points_df = points_df.withColumn('tempSet4Score', F.when(
    ((F.col('Set1') + F.col('Set2')) == 3), F.concat(F.col('P1games').cast("string"), lit("-"), F.col('P2games').cast("string")))
)
points_df = points_df.withColumn('tempSet5Score', F.when(
    ((F.col('Set1') + F.col('Set2')) == 4), F.concat(F.col('P1games').cast("string"), lit("-"), F.col('P2games').cast("string")))
)

points_df = (points_df.withColumn('Set1Score', F.last(F.col('tempSet1Score'), ignorenulls=True).over(windowSpec))
             .withColumn('Set2Score', F.last(F.col('tempSet2Score'), ignorenulls=True).over(windowSpec))
             .withColumn('Set3Score', F.last(F.col('tempSet3Score'), ignorenulls=True).over(windowSpec))
             .withColumn('Set4Score', F.last(F.col('tempSet4Score'), ignorenulls=True).over(windowSpec))
             .withColumn('Set5Score', F.last(F.col('tempSet5Score'), ignorenulls=True).over(windowSpec))
             ).drop('tempSet1Score', 'tempSet2Score', 'tempSet3Score', 'tempSet4Score', 'tempSet5Score')

points_df = (points_df.withColumn('MatchScore', F.concat_ws(" ", F.col('Set1Score'), F.col('Set2Score'), F.col('Set3Score'), F.col('Set4Score'), F.col('Set5Score')))).drop('Set1Score', 'Set2Score', 'Set3Score', 'Set4Score', 'Set5Score', 'P1gamesrank', 'P1games', 'P2games', 'P1sets', 'P2sets')

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

score = points_df.orderBy('match_id', 'Pt').groupBy(
    'match_id').agg(
    F.last('MatchScore').alias('match_score')
)

serve_data = points_df.groupBy(
        'match_id', 'Svr').agg(
        F.round((100 * F.sum((~F.col('1st serve fault')).cast('integer')) / F.count('*'))).alias("first serve percent"),
        F.round((100 * F.sum(F.when((F.col('1st serve fault')) & (~F.col('2nd serve fault')), 1).otherwise(0)) / F.sum(F.col('1st serve fault').cast('integer')))).alias("second serve percent"),
        F.sum((F.col('2nd serve fault')).cast('integer')).alias("double faults")
    )
serve_data = serve_data.groupBy('match_id').agg(
    F.first(F.when(F.col('Svr')==1, F.col('first serve percent')), ignorenulls=True).alias('p1_fsp'),
    F.first(F.when(F.col('Svr')==1, F.col('second serve percent')), ignorenulls=True).alias('p1_ssp'),
    F.first(F.when(F.col('Svr')==1, F.col('double faults')), ignorenulls=True).alias('p1_df'),
    F.first(F.when(F.col('Svr')==2, F.col('first serve percent')), ignorenulls=True).alias('p2_fsp'),
    F.first(F.when(F.col('Svr')==2, F.col('second serve percent')), ignorenulls=True).alias('p2_ssp'),
    F.first(F.when(F.col('Svr')==2, F.col('double faults')), ignorenulls=True).alias('p2_df')
)


window = Window().partitionBy('match_id').orderBy(F.desc('Pt'))
match_winner = points_df.withColumn('match_winner', F.row_number().over(window)).where("match_winner == 1")
match_winner = match_winner.withColumn('match_winner', F.col('PtWinner'))
match_winner = match_winner.withColumn('winner', F.when(F.col('match_winner')==1, F.translate(F.split('match_id', '-').getItem(4), '_', ' ')).otherwise(F.translate(F.split('match_id', '-').getItem(5), '_', ' ')))
match_winner = match_winner.withColumn('loser', F.when(F.col('match_winner')==1, F.translate(F.split('match_id', '-').getItem(5), '_', ' ')).otherwise(F.translate(F.split('match_id', '-').getItem(4), '_', ' ')))
matches = matches.join(score, on='match_id', how='left')
matches = matches.join(match_winner.select(['winner', 'loser', 'match_id']), on='match_id', how='left')
matches = matches.join(serve_data, on='match_id', how='left' )
matches = matches.join(match_stats_df, on='match_id', how='left')


p1 = matches.withColumns({
    'Player': F.col('player_1'),
    'Match': F.col('match_id'),
    'first_serve_pctg': F.col('p1_fsp'),
    'second_serve_pctg': F.col('p1_ssp'),
    'double_faults': F.col('p1_df'),
    'win': F.when(F.col('winner')==F.col('player_1'), True).otherwise(False)
}).drop('match_id', 'date', 'gender', 'tournament', 'round', 'player_1', 'player_2', 'winner', 'loser', 'p1_fsp', 'p1_ssp', 'p1_df', 'p2_fsp', 'p2_ssp', 'p2_df')
p2 = matches.withColumns({
    'Player': F.col('player_2'),
    'Match': F.col('match_id'),
    'first_serve_pctg': F.col('p2_fsp'),
    'second_serve_pctg': F.col('p2_ssp'),
    'double_faults': F.col('p2_df'),
    'win': F.when(F.col('winner')==F.col('player_2'), True).otherwise(False)
}).drop('match_id', 'date', 'gender', 'tournament', 'round', 'player_1', 'player_2', 'winner', 'loser', 'p1_fsp', 'p1_ssp', 'p1_df', 'p2_fsp', 'p2_ssp', 'p2_df')

clean = p1.union(p2)

start_time = time.time()
matches.orderBy(F.desc('date')).show()
matches.coalesce(1).write.csv('/Users/chrismckenzie/Downloads/tennisprediction/tennis/data/cleaned_data', header=True, mode='overwrite')
end_time = time.time()
print(end_time - start_time)
