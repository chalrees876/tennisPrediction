# tennis/management/commands/ComputeMatchPredictions.py

from django.core.management import BaseCommand
from django.db import transaction
import datetime

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
        parser.add_argument(
            "--debug",
            action="store_true",
            help="Show detailed debug output.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        qs = PlayerMatch.objects.filter(tournament__event_type_type="Atp Singles")
        if options["only_missing"]:
            qs = qs.filter(prediction__isnull=True)

        total = qs.count()
        self.stdout.write(f"Computing predictions for {total} matches...")

        # Count upcoming vs completed
        upcoming = qs.filter(winner__isnull=True, date__gte=datetime.date.today()).count()
        completed = qs.filter(winner__isnull=False).count()
        self.stdout.write(f"  - Upcoming matches: {upcoming}")
        self.stdout.write(f"  - Completed matches: {completed}")

        skipped = 0
        created = 0
        updated = 0

        for i, match in enumerate(qs.iterator(), start=1):
            if i % 50 == 0:
                self.stdout.write(f"Processed {i}/{total} matches...")

            is_upcoming = match.winner is None and match.date >= datetime.date.today()
            match_type = "UPCOMING" if is_upcoming else "COMPLETED"

            if options["debug"]:
                self.stdout.write(
                    f"\n{match_type} Match {match.pk}: {match.first_player.name} vs {match.second_player.name} on {match.date}")

            try:
                preds = predict_for_match(match)
                if options["debug"]:
                    self.stdout.write(f"  Successfully computed predictions:")
                    self.stdout.write(f"    ens_prob: {preds['ens_prob']:.3f}")
                    self.stdout.write(f"    log_reg_prob: {preds['log_reg_prob']:.3f}")
                    self.stdout.write(f"    rf_prob: {preds['rf_prob']:.3f}")
            except ValueError as e:
                if options["debug"]:
                    self.stdout.write(f"  ERROR: {e}")
                skipped += 1
                continue
            except Exception as e:
                if options["debug"]:
                    self.stdout.write(f"  UNEXPECTED ERROR: {e}")
                skipped += 1
                continue

            # Save the prediction
            try:
                obj, created_flag = MatchPrediction.objects.update_or_create(
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

                if created_flag:
                    created += 1
                    if options["debug"]:
                        self.stdout.write(f"  ✓ Created new prediction (ID: {obj.match_id})")
                else:
                    updated += 1
                    if options["debug"]:
                        self.stdout.write(f"  ✓ Updated existing prediction")

            except Exception as e:
                if options["debug"]:
                    self.stdout.write(f"  ERROR saving prediction: {e}")
                skipped += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone. Created: {created}, Updated: {updated}, Skipped: {skipped}"
            )
        )