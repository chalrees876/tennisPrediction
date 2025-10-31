import datetime
import joblib
import pandas as pd
from django.core.management import BaseCommand
from tennis.ml.MachineLearning import MachineLearningModels
from tennis.ml.TennisDataCollector import TennisDataCollector


class Command(BaseCommand):
    def handle(self, *args, **options):
        fe = TennisDataCollector(start_date="2010-01-01", end_date=datetime.date.today())
        match_features = fe.collect_training_data()
        df = pd.read_csv('tennis/data/training_data.csv')
        learn = MachineLearningModels(df).log_reg_train()
        joblib.dump(learn, 'tennis/models/machine_learning.pkl')