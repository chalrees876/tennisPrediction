# ATP Tennis Match Predictor

A full-stack machine learning application that predicts ATP tennis match outcomes using player performance data, custom-engineered features, and an ensemble model. Built with Django, scikit-learn, and a live PostgreSQL database.

**Live demo database available** — see setup instructions below.

---

## Overview

Predicting tennis match outcomes is a non-trivial problem. Unlike team sports, tennis outcomes depend heavily on player-specific variables: serve dominance, break point conversion, surface preference, fatigue from recent match load, and head-to-head momentum. This project builds a data pipeline and ML system to capture those dynamics using only **pre-match observable features** — no leakage from in-match data.

The system ingests historical ATP match data, engineers 12+ differential features per match, trains a calibrated ensemble model, and serves predictions through a Django web application.

---

## Features

**Data Pipeline**
- Automated ingestion of historical ATP match data (serve stats, return stats, match outcomes)
- ELO rating scraping from tennisabstract.com via Selenium
- Django management commands for end-to-end rebuild: data import → feature engineering → model training → prediction generation

**Feature Engineering**
All features are computed as **player differentials** (player minus opponent), strictly using data prior to match date to prevent leakage:

| Feature | Description |
|---|---|
| `h2h_win_ratio_diff` | Head-to-head win ratio (shrunk toward 0.5 for small samples) |
| `h2h_recent_momentum` | Exponentially weighted recent H2H outcomes (decay=0.8) |
| `recent_form_diff` | Win rate over last 20 days |
| `win_rate_diff` | Overall win rate over 250-day rolling window |
| `serve_rating_diff` | Composite serve rating (70% first serve win % + 30% second serve win %) |
| `bp_conv_pctg_diff` | Break point conversion percentage |
| `dom_ratio_diff` | Dominance ratio (service points won / return points won) |
| `fatigue_diff` | Match load over last 14 days |
| `match_volume_14d_diff` | Number of matches played in last 14 days |
| `win_rate_hard/clay/grass_diff` | Surface-specific win rate differentials |

**Model**
- Logistic Regression with isotonic calibration (TimeSeriesSplit cross-validation)
- Random Forest Classifier
- Ensemble: optimal weighted average of LR + RF probabilities (grid-searched)
- Temporal train/test split — no shuffle — to respect time ordering of matches
- Evaluation: ROC-AUC, Brier score, permutation feature importance

**Application**
- Django web app with player pages, upcoming match predictions, head-to-head comparisons, and completed match results
- PostgreSQL backend (read-only demo database available)
- Prediction stored per-match and served via templated views

---

## Results

| Model | ROC-AUC |
|---|---|
| Logistic Regression (calibrated) | ~0.72 |
| Random Forest | ~0.71 |
| Ensemble | ~0.72 |

*Evaluated on a held-out temporal test set (last 20% of matches by date).*

Top features by permutation importance: `serve_rating_diff`, `h2h_win_ratio_diff`, `recent_form_diff`

---

## Tech Stack

- **Backend:** Django, PostgreSQL (via psycopg), SQLite (local dev)
- **ML:** scikit-learn, pandas, numpy, joblib
- **Data Collection:** Selenium, Playwright
- **Deployment:** AWS (boto3), Neon serverless PostgreSQL

---

## Setup

### Local Development

```bash
git clone https://github.com/chalrees876/tennisPrediction.git
cd tennisPrediction

python -m venv venv
source venv/bin/activate

pip install -r requirements.txt
```

Create a `.env` file:
```
DJANGO_SETTINGS_MODULE=config.settings_dev
SECRET_KEY=your-secret-key
```

Run migrations and start the server:
```bash
python manage.py migrate
python manage.py runserver
```

### Demo Database (Read-Only)

To run against the live demo database, set the following in `.env`:
```
DJANGO_SETTINGS_MODULE=config.settings_prod
DATABASE_URL=postgresql://readonly_user:limited_password@ep-proud-tooth-ahsdsq47-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require
SECRET_KEY=your-secret-key
```

---

## ML Pipeline

To retrain the model from scratch:

```bash
# Build features + train model + generate predictions
python manage.py TrainModel --build_features True --rebuild True

# Train only (skip data rebuild)
python manage.py TrainModel

# Import ELO ratings
python manage.py EloImport
```

---

## Project Structure

```
tennisPrediction/
├── tennis/
│   ├── ml/
│   │   ├── MachineLearning.py       # Ensemble model: LR + RF + calibration
│   │   ├── feature_engineering.py   # Pre-match feature computation (leakage-free)
│   │   └── TennisDataCollector.py   # Collects and stores training data
│   ├── management/commands/
│   │   ├── TrainModel.py            # End-to-end training pipeline
│   │   ├── EloImport.py             # Scrapes ELO ratings
│   │   ├── PlayerMatchData.py       # Historical match data import
│   │   └── UpcomingMatchData.py     # Upcoming match data import
│   ├── models.py                    # Django ORM models
│   └── templates/                   # Match, player, H2H views
├── config/                          # Django settings (dev/prod)
└── requirements.txt
```

---

## What I'd Do Next

- **Add ELO as a feature:** ELO ratings are scraped and stored but not yet incorporated into the feature vector. Prior work (e.g., FiveThirtyEight) shows ELO is one of the strongest single predictors.
- **Surface-specific models:** Train separate models per surface rather than surface win rate differentials as features.
- **Richer serve/return features:** First serve speed, ace rate, and double fault rate are available in some ATP datasets and likely informative.
- **Calibration evaluation:** Plot reliability diagrams to validate probability calibration beyond Brier score.

---

## Data Source

Historical ATP match data imported via automated pipeline. ELO ratings from [tennisabstract.com](https://tennisabstract.com).
