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

points_df =