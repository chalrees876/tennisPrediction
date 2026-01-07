import datetime
import joblib
import pandas as pd
from django.core.management import BaseCommand
from tennis.ml.MachineLearning import MachineLearningModels
from tennis.ml.TennisDataCollector import TennisDataCollector


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            '--rebuild',
            type=bool,
            default=False,
            help='Rebuild training data before training model',
        )
    def handle(self, *args, **options):
        start_time = datetime.datetime.now()
        TennisDataCollector(start_date="2018-01-01", end_date=datetime.date.today(), rebuild = options['rebuild']).collect_training_data()
        learn = MachineLearningModels().log_reg_train()
        ml = MachineLearningModels()
        bundle=ml.log_reg_train()
        ml.save_model(bundle)
        ml.generate_all_predictions()
        joblib.dump(learn, 'tennis/models/machine_learning.pkl')
        end_time = datetime.datetime.now()
        print('Time taken:', end_time - start_time)