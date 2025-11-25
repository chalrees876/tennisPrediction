# tennis/management/commands/ComputeMatchPredictions.py

from django.core.management import BaseCommand
from django.db import transaction

from tennis.models import PlayerMatch, MatchPrediction
from tennis.ml.predictor import predict_for_match


class Command(BaseCommand):
    help = "Compute and store model predictions for matches."

    def add_arguments(self, parser):
        parser.add_argument(
            "--only-missing",
            action="store_true",
            help="Only compute predictions for matches without predictions.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        qs = PlayerMatch.objects.filter(tournament__event_type_type="Atp Singles")
        if options["only_missing"]:
            qs = qs.filter(prediction__isnull=True)

        total = qs.count()
        self.stdout.write(f"Computing predictions for {total} matches...")
        skipped = 0

        for i, match in enumerate(qs.iterator(), start=1):
            if i % 200 == 0:
                self.stdout.write(f"Processed {i}/{total} matches...")

            try:
                preds = predict_for_match(match)
            except ValueError:
                skipped += 1
                continue

            MatchPrediction.objects.update_or_create(
                match=match,
                defaults={
                    "log_reg_prob": preds["log_reg_prob"],
                    "rf_prob": preds["rf_prob"],
                    "ens_prob": preds["ens_prob"],
                    "log_reg_ml_p1": preds["log_reg_ml_p1"],
                    "log_reg_ml_p2": preds["log_reg_ml_p2"],
                    "rf_ml_p1": preds["rf_ml_p1"],
                    "rf_ml_p2": preds["rf_ml_p2"],
                    "ens_ml_p1": preds["ens_ml_p1"],
                    "ens_ml_p2": preds["ens_ml_p2"],
                },
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Done computing match predictions. Skipped {skipped} matches with no features."
            )
        )
