import glob
import os
import subprocess

from pyspark.sql import SparkSession, Window
from pyspark.sql import functions as F
from pyspark.sql.functions import lit
from pyspark.sql.types import StringType, IntegerType, StructField, BooleanType, StructType

if "JAVA_HOME" not in os.environ or "17" not in os.environ["JAVA_HOME"]:
    os.environ["JAVA_HOME"] = subprocess.check_output(
        ["/usr/libexec/java_home", "-v", "17"]
    ).decode().strip()

current_path = os.path.abspath(__file__)
tennis_app_path = os.path.dirname(os.path.dirname(os.path.dirname(current_path)))
data_path = (tennis_app_path + "/data/cleaned_data/matches.csv")

spark = (SparkSession.builder
         .appName("scoringpyspark")
         .config("spark.sql.shuffle.partitions", "16")
         .getOrCreate()
         )

game_pt = ['40-0',
       '40-15',
       '40-30',
       'AD-40',]
break_pt = ['0-40',
       '15-40',
       '30-40',
       '40-AD']
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
points_df = spark.read.option("multiLine", True).option("quote", '"').option("escape", "'").option("header", True).schema(schema).csv(csv_files)

windowSpec = Window.partitionBy('match_id').orderBy('Pt')
points_df.show()
points_df = points_df.withColumns({
    'P1gamesrank': lit(0),
    'P1games': lit(0),
    'P2games':lit(0),
    'P1sets':lit(0),
    'P2sets': lit(0)})

points_df = points_df.withColumn('P1gamesrank', F.when(
    (F.col('Pts').isin(game_pt) & (F.col('PtWinner') == 1) & (F.col('Svr') == 1)),
    lit(1)).otherwise(lit(0)))

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
                     (F.lead(F.col('Gm1'), 1, 0).over(windowSpec) == 0) &
                     (F.lag(F.col('Gm1'), 1, 0).over(windowSpec) != 0) &
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


