# TennisPredict

**Author:** [Christopher McKenzie](https://github.com/chalrees876)  

TennisPredict is a full-stack machine learning web application that forecasts professional tennis match outcomes using historical player data and predictive modeling.  
The platform combines statistical analysis, automated data ingestion, and intuitive data visualization to help users understand player performance trends and match probabilities.

---

## Overview

TennisPredict analyzes ATP and WTA match data to generate real-time win predictions and matchup insights.  
The app integrates an automated ETL pipeline that continuously scrapes and processes statistics from [TennisAbstract.com](https://www.tennisabstract.com) and other public data sources.  
Machine learning models (Logistic Regression, Random Forest, and Ensemble methods) compute win probabilities based on player form, surface preference, and head-to-head performance.

---

## Key Features

### Match Predictions
- Predicts the winner of upcoming ATP and WTA matches using ensemble ML models.
- Displays predicted probabilities, American-style betting odds, and model confidence levels.
- Adjusts predictions dynamically based on the latest results and player statistics.

### Player Insights
- View historical performance metrics, surface-specific records, and form trends.
- Track win/loss streaks, serve and return efficiency, and head-to-head comparisons.

### Model Dashboard
- Interactive graphs showing model accuracy, confusion matrices, and AUC/ROC scores.
- Transparent view of how each model performs over time with retraining updates.

### Automated Data Pipeline
- Nightly ETL (Extract, Transform, Load) jobs update match data and model features.
- Data scraped directly from **TennisAbstract.com** using Playwright automation.
- Cleaned, structured, and stored in a **PostgreSQL** database before feeding ML models.

---

## Tech Stack

| Layer | Technologies |
|-------|---------------|
| **Frontend** | Django Templates (HTML, CSS, JS) |
| **Backend** | Django (Python), REST API |
| **Database** | PostgreSQL |
| **Machine Learning** | scikit-learn, pandas, NumPy, Matplotlib, Seaborn |
| **Automation / ETL** | Playwright, cron-scheduled scripts |
| **Deployment** | Gunicorn + Nginx on AWS EC2 (Ubuntu) |
| **Data Source** | [TennisAbstract.com](https://www.tennisabstract.com) |

---

## How It Works

### 1. **Data Extraction**
Playwright scripts scrape raw match data, player statistics, and historical results from TennisAbstract.com.  
Data includes:
- Player identifiers and match dates  
- Tournament surface and round  
- Serve/return points won  
- Match outcomes and Elo ratings  

### 2. **Data Transformation**
- Cleans raw HTML tables into structured pandas DataFrames.  
- Computes rolling player metrics such as:
  - Last-14-day win rate
  - Surface win percentage
  - Average serve efficiency
  - Historical Elo/ranking trends  
- Removes look-ahead bias to ensure all features are based only on **past** matches.

### 3. **Model Training**
Three models are trained and evaluated:
- **Logistic Regression** (baseline probability model)  
- **Random Forest** (captures nonlinear interactions)  
- **Ensemble Blended Model** (weighted combination of both)  

Metrics such as **ROC-AUC**, **accuracy**, and **calibration** are tracked to tune thresholds and assess reliability.

### 4. **Prediction & Visualization**
The latest trained models predict the outcome of upcoming matches.  
Predictions are displayed with:
- **Win probability**
- **Fair betting odds**
- **Historical matchup stats**
- **Model-confidence graphs**

---

## Example Output

| Player 1 | Player 2 | Model Prediction | Win Probability | Odds |
|-----------|-----------|------------------|-----------------|------|
| Alcaraz   | Djokovic  | Djokovic         | 57.3%           | +130 |
| Swiatek   | Sabalenka | Swiatek          | 62.8%           | -170 |

---
