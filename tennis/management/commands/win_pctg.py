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


points_df.show()

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