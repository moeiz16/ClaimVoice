"""Train the loss-type classifier (`make train`, or `python -m claimvoice.nlu.train`). CPU, seconds, fixed seeds.

1. Corpus: the generated paraphrases (`nlu.corpus.generate`) plus the main scripted callers' turns. The held-out
   caller sets are never read here.
2. Out-of-lexicon validation: a model is fitted on the training share of every word list and the main callers, and
   scored on sentences built only from the validation share (verbs, objects, causes and places it has not seen).
3. Calibration: one temperature for the softmax, fitted on that validation set by log loss; expected calibration
   error before and after.
4. Thresholds, on the same validation set: `accept` is the lowest confidence at which a loss type it names is wrong
   at most 2 times in 100 (a wrong value costs more than a question); `confirm` is the lowest confidence at which the
   named type is still right at least 7 times in 10, so asking "is this about water damage?" is worth a turn. Below
   that the line asks which kind of loss it was.
5. The shipped model is refitted on everything (both shares and the callers) with the same settings, temperature and
   thresholds, and exported to `nlu/artifacts/loss_type_v1.json.gz` with its metrics beside it (no timestamps).
"""

from __future__ import annotations

import gzip
import io
import json
import statistics
import time
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score

from claimvoice.nlu import lexicon as lx
from claimvoice.nlu.corpus import SEED, Example, generate, scripted_turns
from claimvoice.nlu.model import ARTIFACTS, MODEL_PATH, LossTypeModel, features

METRICS_PATH = ARTIFACTS / "loss_type_v1.metrics.json"
C = 4.0
MIN_DF = 2
MAX_FEATURES = 24000
MAX_WRONG_ACCEPTED = 0.02
MIN_RIGHT_CONFIRMED = 0.70
GRID = [round(0.30 + 0.01 * i, 2) for i in range(70)]  # 0.30 .. 0.99


def _fit(texts: list[str], labels: list[str]) -> tuple[TfidfVectorizer, LogisticRegression]:
    vec = TfidfVectorizer(
        analyzer=features, sublinear_tf=True, min_df=MIN_DF, max_features=MAX_FEATURES, dtype=np.float64
    )
    x = vec.fit_transform(texts)
    clf = LogisticRegression(C=C, max_iter=3000, class_weight="balanced", random_state=SEED)
    clf.fit(x, labels)
    return vec, clf


def _softmax(z: np.ndarray) -> np.ndarray:
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    out: np.ndarray = e / e.sum(axis=1, keepdims=True)
    return out


def _ece(probs: np.ndarray, correct: np.ndarray, bins: int = 10) -> float:
    conf = probs.max(axis=1)
    total = 0.0
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        mask = (conf > lo) & (conf <= hi)
        if mask.any():
            total += mask.mean() * abs(correct[mask].mean() - conf[mask].mean())
    return float(total)


def _temperature(logits: np.ndarray, y: np.ndarray) -> float:
    best_t, best_nll = 1.0, float("inf")
    for t in [round(0.25 + 0.05 * i, 2) for i in range(76)]:  # 0.25 .. 4.0
        p = _softmax(logits / t)
        nll = float(-np.log(np.clip(p[np.arange(len(y)), y], 1e-12, 1.0)).mean())
        if nll < best_nll:
            best_t, best_nll = t, nll
    return best_t


def _thresholds(pred: list[str], conf: np.ndarray, truth: list[str]) -> dict[str, float]:
    named = [i for i, p in enumerate(pred) if p != lx.NONE]
    accept = 0.99
    for t in GRID:
        kept = [i for i in named if conf[i] >= t]
        if kept and sum(pred[i] != truth[i] for i in kept) / len(kept) <= MAX_WRONG_ACCEPTED:
            accept = t
            break
    confirm = accept
    for t in GRID:
        if t >= accept:
            break
        band = [i for i in named if t <= conf[i] < accept]
        if band and sum(pred[i] == truth[i] for i in band) / len(band) >= MIN_RIGHT_CONFIRMED:
            confirm = t
            break
    return {"accept": accept, "confirm": confirm}


def _export(vec: TfidfVectorizer, clf: LogisticRegression, temperature: float, thresholds: dict[str, float]) -> dict:
    vocab = vec.get_feature_names_out().tolist()
    coef = clf.coef_.T  # (features, classes)
    return {
        "version": 1,
        "labels": [str(c) for c in clf.classes_],
        "temperature": temperature,
        "thresholds": thresholds,
        "sublinear_tf": True,
        "features": vocab,
        "idf": [round(float(v), 5) for v in vec.idf_],
        "coef": [[round(float(v), 5) for v in row] for row in coef],
        "intercept": [round(float(v), 5) for v in clf.intercept_],
    }


def _write_gz(doc: dict[str, Any], path: Path) -> int:
    raw = json.dumps(doc, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0, compresslevel=9) as gz:  # mtime=0: same bytes every run
        gz.write(raw)
    path.write_bytes(buf.getvalue())
    return len(buf.getvalue())


def _per_language(examples: list[Example], pred: list[str]) -> dict[str, float]:
    out: dict[str, float] = {}
    for lang in ("en", "fr"):
        idx = [i for i, e in enumerate(examples) if e.language == lang]
        out[lang] = round(sum(pred[i] == examples[i].label for i in idx) / max(1, len(idx)), 4)
    return out


def main() -> dict[str, Any]:
    started = time.perf_counter()
    train_gen = generate(split="train")
    val_gen = generate(split="val", scale=0.5)
    calls = scripted_turns()
    train = train_gen + calls
    vec, clf = _fit([e.text for e in train], [e.label for e in train])
    labels = [str(c) for c in clf.classes_]
    y_val = np.array([labels.index(e.label) for e in val_gen])
    logits = clf.decision_function(vec.transform([e.text for e in val_gen]))
    raw_probs = _softmax(logits)
    temperature = _temperature(logits, y_val)
    probs = _softmax(logits / temperature)
    pred = [labels[i] for i in probs.argmax(axis=1)]
    truth = [e.label for e in val_gen]
    correct = np.array([p == t for p, t in zip(pred, truth, strict=True)])
    thresholds = _thresholds(pred, probs.max(axis=1), truth)
    conf = probs.max(axis=1)
    named = [i for i, p in enumerate(pred) if p != lx.NONE]
    accepted = [i for i in named if conf[i] >= thresholds["accept"]]
    confirmed = [i for i in named if thresholds["confirm"] <= conf[i] < thresholds["accept"]]
    described = [i for i, t in enumerate(truth) if t != lx.NONE]
    validation = {
        "sentences": len(val_gen),
        "accuracy": round(float(correct.mean()), 4),
        "macro_f1": round(float(f1_score(truth, pred, average="macro")), 4),
        "by_language": _per_language(val_gen, pred),
        "ece_before": round(_ece(raw_probs, correct), 4),
        "ece_after": round(_ece(probs, correct), 4),
        "accepted_share_of_descriptions": round(sum(1 for i in accepted if truth[i] != lx.NONE) / len(described), 4),
        "wrong_when_accepted": round(sum(pred[i] != truth[i] for i in accepted) / max(1, len(accepted)), 4),
        "right_when_confirmed": round(sum(pred[i] == truth[i] for i in confirmed) / max(1, len(confirmed)), 4),
        "none_taken_as_a_loss": round(
            sum(1 for i in accepted if truth[i] == lx.NONE) / max(1, sum(t == lx.NONE for t in truth)), 4
        ),
    }
    # the shipped model: everything, same settings, the temperature and thresholds fitted above
    everything = generate(split="all") + calls
    vec_all, clf_all = _fit([e.text for e in everything], [e.label for e in everything])
    doc = _export(vec_all, clf_all, temperature, thresholds)
    shipped = LossTypeModel(doc)
    sample = [e.text for e in val_gen[:2000]]
    timings = []
    for text in sample:
        t0 = time.perf_counter()
        shipped.predict(text)
        timings.append((time.perf_counter() - t0) * 1000)
    timings.sort()
    meta = {
        "corpus": {
            "generated_train": len(train_gen),
            "generated_validation": len(val_gen),
            "generated_all": len(everything) - len(calls),
            "scripted_turns": len(calls),
            "by_label": dict(sorted(Counter(e.label for e in everything).items())),
            "by_language": dict(sorted(Counter(e.language for e in everything).items())),
        },
        "settings": {"C": C, "min_df": MIN_DF, "max_features": MAX_FEATURES, "seed": SEED},
        "features": len(doc["features"]),
        "temperature": temperature,
        "thresholds": thresholds,
        "validation_out_of_lexicon": validation,
        "inference_ms": {
            "p50": round(statistics.median(timings), 3),
            "p95": round(timings[int(0.95 * (len(timings) - 1))], 3),
        },
    }
    doc["meta"] = {"validation": validation, "thresholds": thresholds}
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    size = _write_gz(doc, MODEL_PATH)
    meta["artifact_bytes"] = size
    print(json.dumps(meta, indent=2, ensure_ascii=False))
    meta.pop("inference_ms")  # timings vary by machine; the eval measures them per turn
    METRICS_PATH.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {MODEL_PATH.name} ({size / 1024:.0f} KB) in {time.perf_counter() - started:.1f}s")
    return meta


if __name__ == "__main__":
    main()
