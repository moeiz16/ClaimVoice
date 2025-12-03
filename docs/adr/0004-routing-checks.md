# ADR 0004: Routing checks: XGBoost size and closer-look models with rules, reasons, fairness and two sign-offs

**Status:** accepted

## Context
At hang-up each claim needs a first owner: fast-track (simple, quick to price), an adjuster, or a closer look by
special investigations. Insurers that use models for this must govern them (NAIC Model Bulletin), test them for
unfair discrimination, explain them, and must not let them deny claims. The models have to train and run on a laptop
CPU.

## Decision
- **Two checks, two models.** The *size check* predicts the probability that a claim is large or complex (top
  decile of cost, or needing an adjuster's site visit); the *closer-look check* predicts the probability that review
  by special investigations would find something worth acting on.
- **Data.** Synthetic intake records shaped like what the line collects, with claim costs drawn from freMTPL2's real
  severity distribution and documented, independently injected fraud patterns (docs/DATA.md). A freMTPL2-only
  large-claim benchmark is reported alongside so the method is shown on public data.
- **Leakage-safe split** by loss month (train before October 2025, validate October–November, test December).
- **Baselines first:** logistic regression (scorecard-style) and a random forest; **XGBoost** challenger tuned with
  Optuna on the validation months; **isotonic calibration**; thresholds chosen for fixed targets (size: recall of
  large/complex claims ≥ 0.90; closer look: referral rate ≤ 8 %).
- **Rules win** over scores: urgent safety and possible injuries never go to fast-track; a closer-look referral needs
  at least two signs; a person can change any route with a reason.
- **Reasons** from SHAP, translated into plain sentences (EN/FR) and linked to the moment in the call; top 3 shown.
  SHAP stability across bootstrap refits is a gate.
- **Fairness** by region, language and age band, which are never inputs (nor postal code, date of birth, names, or
  any voice-derived signal such as stress, accent or speech rate). Gates: closer-look rate within ±1.5 points of the
  overall rate per group; fast-track rate within ±5 points.
- **Monitoring:** PSI on inputs and scores weekly (Watch 0.10, Act 0.25; Act pauses fast-track for that check);
  performance once outcomes are known.
- **Registry and governance:** MLflow (SQLite + `mlruns/`, git-ignored) for runs; the API reads a `model_versions`
  mirror. A candidate goes into use only when every gate passes and **two different people sign off**: a claims
  supervisor and compliance (model risk). Fact sheets (model cards) are generated without run timestamps.

## Consequences
- Synthetic labels make the closer-look check's absolute performance a statement about our generator, not about the
  world; the fact sheet says so, and the value shown is the pipeline: calibration, reasons, fairness, monitoring and
  sign-off.
- Training is one CPU job (`make train`, under a minute); committed artefacts let a fresh checkout score without
  retraining.
- Disagreements between a person and a check are recorded (route overrides) and feed the next version's review.
