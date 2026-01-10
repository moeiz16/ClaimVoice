"""The loss-type classifier: character and word n-gram TF-IDF with multinomial logistic regression, temperature-scaled.

Training (`nlu.train`) fits scikit-learn's `TfidfVectorizer` with `analyzer=features` and a `LogisticRegression`, then
exports the vocabulary, IDF weights, coefficients and the fitted temperature to a small gzipped JSON file. Inference
here is plain Python over that file (no scikit-learn import on the call path): the same `features` function, sublinear
term frequency times IDF, L2 normalisation, a sparse dot product and a softmax at the fitted temperature. A unit test
checks it against the scikit-learn pipeline it was exported from.
"""

from __future__ import annotations

import gzip
import itertools
import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

ARTIFACTS = Path(__file__).parent / "artifacts"
MODEL_PATH = ARTIFACTS / "loss_type_v1.json.gz"

_WORD = re.compile(r"[a-zà-ÿ0-9]+(?:'[a-zà-ÿ]+)?", re.IGNORECASE)
_DIGITS = re.compile(r"\d")


def normalise(text: str) -> str:
    t = text.lower().replace("’", "'").replace("`", "'")
    t = re.sub(r"\blm-[a-z]{2}-\d+\b", " policynumber ", t)
    return _DIGITS.sub("0", t)


def features(text: str) -> list[str]:
    """Word unigrams and bigrams, and character 3- to 5-grams inside word boundaries (robust to spelling, inflection
    and English/French cognates: "flood", "flooded", "inondé", "inondation" share pieces)."""
    words = _WORD.findall(normalise(text))
    out = ["w:" + w for w in words]
    out += ["b:" + a + "_" + b for a, b in itertools.pairwise(words)]
    for w in words:
        padded = f"<{w}>"
        for n in (3, 4, 5):
            if len(padded) >= n:
                out += ["c:" + padded[i : i + n] for i in range(len(padded) - n + 1)]
    return out


@dataclass(frozen=True, slots=True)
class Prediction:
    label: str
    probability: float
    probabilities: dict[str, float]
    cue: tuple[int, int] | None  # character span of the word that pushed hardest towards the label, if any


class LossTypeModel:
    def __init__(self, doc: dict[str, Any]) -> None:
        self.labels: list[str] = list(doc["labels"])
        self.temperature: float = float(doc["temperature"])
        self.thresholds: dict[str, float] = {k: float(v) for k, v in doc["thresholds"].items()}
        self.sublinear: bool = bool(doc.get("sublinear_tf", True))
        vocab: list[str] = doc["features"]
        idf: list[float] = doc["idf"]
        coef: list[list[float]] = doc["coef"]
        self.index = {f: i for i, f in enumerate(vocab)}
        self.idf = idf
        self.coef = coef
        self.intercept: list[float] = list(doc["intercept"])
        self.meta: dict[str, Any] = dict(doc.get("meta", {}))

    @classmethod
    def load(cls, path: Path = MODEL_PATH) -> LossTypeModel:
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            return cls(json.load(fh))

    def scores(self, text: str) -> list[float]:
        counts = Counter(f for f in features(text) if f in self.index)
        weights: dict[int, float] = {}
        for f, c in counts.items():
            i = self.index[f]
            tf = 1.0 + math.log(c) if self.sublinear else float(c)
            weights[i] = tf * self.idf[i]
        norm = math.sqrt(sum(w * w for w in weights.values())) or 1.0
        out = list(self.intercept)
        for i, w in weights.items():
            row = self.coef[i]
            x = w / norm
            for k in range(len(out)):
                out[k] += x * row[k]
        return out

    def predict(self, text: str) -> Prediction:
        raw = self.scores(text)
        z = [s / self.temperature for s in raw]
        top = max(z)
        exp = [math.exp(v - top) for v in z]
        total = sum(exp)
        probs = {lab: e / total for lab, e in zip(self.labels, exp, strict=True)}
        label = max(probs, key=lambda k: probs[k])
        return Prediction(label, probs[label], probs, self._cue(text, self.labels.index(label)))

    def _cue(self, text: str, k: int) -> tuple[int, int] | None:
        """The word whose own features push hardest towards class k (the span a value points back at)."""
        best: tuple[float, tuple[int, int]] | None = None
        for m in _WORD.finditer(text):
            w = normalise(m.group(0))
            pushed = 0.0
            for f in features(w):
                i = self.index.get(f)
                if i is not None:
                    row = self.coef[i]
                    pushed += row[k] - max(row[j] for j in range(len(row)) if j != k)
            if pushed > 0 and (best is None or pushed > best[0]):
                best = (pushed, m.span())
        return best[1] if best else None


@cache
def loaded() -> LossTypeModel | None:
    """The committed model, or None when it hasn't been trained (`make train`): the rules still answer."""
    if not MODEL_PATH.exists():
        return None
    return LossTypeModel.load()
