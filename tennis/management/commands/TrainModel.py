import datetime
import joblib
import pandas as pd
from django.core.management import BaseCommand
from tennis.ml.MachineLearning import MachineLearningModels
from tennis.ml.TennisDataCollector import TennisDataCollector
from tennis.ml.feature_engineering import TennisFeatureEngineer
from tennis.models import PlayerMatch


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            '--rebuild',
            type=bool,
            default=True,
            help='Rebuild training data before training model',
        )
        parser.add_argument(
            '--build_features',
            type=bool,
            default=False,
            help='Build match features before training model',
        )
    def handle(self, *args, **options):
        start_time = datetime.datetime.now()
        # Step 1: Build MatchFeatures
        if options['build_features']:
            self.stdout.write("Building features...")
            TennisDataCollector(
                start_date="1999-01-01",
                end_date=datetime.date.today(),
                rebuild=options['rebuild']
            ).collect_training_data()
        else:
            self.stdout.write("Skipping feature building...")
            
        # Step 2: Train model
        self.stdout.write("\nTraining model...")
        ml = MachineLearningModels()
        bundle = ml.log_reg_train()

        # Step 3: Save model
        model_path = 'tennis_model.joblib'
        ml.save_model(bundle, path=model_path)

        # Step 4: Generate predictions
        self.stdout.write("\nGenerating predictions...")
        result = ml.generate_all_predictions(bundle=bundle)

        end_time = datetime.datetime.now()

        self.stdout.write(self.style.SUCCESS(
            f"\nCompleted in {end_time - start_time}\n"
            f"Predictions: {result['success']} success, {result['errors']} errors"
        ))