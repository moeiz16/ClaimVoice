"""Classical ML at hang-up: claim severity/complexity routing and a fraud-indicator score for SIU referral.

XGBoost challengers against logistic-regression and random-forest baselines; Optuna tuning; isotonic calibration; SHAP
reasons in plain words (EN/FR); fairness gaps by region, language and age band (testing only, never features); model
cards; MLflow tracking and registry (local SQLite + mlruns/); PSI drift; champion/challenger promotion with sign-off.
See docs/adr/0004-triage-models.md and docs/API_CONTRACT.md Part 6."""
