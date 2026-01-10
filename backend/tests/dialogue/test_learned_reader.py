"""The learned layer of the offline reader: the generated corpus, the classifier export, the confirm-or-ask rule in the
engine, and the lexicon-backed extractors."""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

import pytest
import yaml

from claimvoice.dialogue.machine import Say
from claimvoice.dialogue.slots import SLOT_CATALOG
from claimvoice.dialogue.stages import Stage
from claimvoice.nlu import lexicon as lx
from claimvoice.nlu.base import NluRequest, SlotSpec
from claimvoice.nlu.corpus import _in_split, generate
from claimvoice.nlu.model import LossTypeModel, Prediction, features, loaded
from claimvoice.nlu.offline import OfflineUnderstanding

from .helpers import GORD_START, call

NOW = datetime(2026, 1, 8, 7, 42)
CALLERS = Path(__file__).resolve().parents[3] / "eval" / "callers"


def request(text: str, *, stage: str = "consent", keys: tuple[str, ...] = ("loss_type",), asked: str | None = None):
    specs = [SlotSpec(k, SLOT_CATALOG[k].kind if k in SLOT_CATALOG else "text") for k in keys]
    return NluRequest(stage=stage, utterance=text, language="en", expecting=specs, asked=asked, now=NOW)


# ------------------------------------------------------------------ corpus


def test_the_generator_is_seeded_and_repeatable():
    a = generate(split="train", scale=0.05)
    b = generate(split="train", scale=0.05)
    assert [e.text for e in a] == [e.text for e in b]
    assert {e.label for e in a} == set(lx.LABELS)
    assert {e.language for e in a} == {"en", "fr"}


def test_validation_words_are_never_in_the_training_share():
    for words in (lx.COLLISION_VERBS_EN, lx.WIND_VERBS_EN, lx.THEFT_ITEMS_EN, lx.ROOMS_FR):
        val = {w for w in words if _in_split(w, "val")}
        train = {w for w in words if _in_split(w, "train")}
        assert val and train and not val & train


def test_no_held_out_sentence_is_in_the_training_corpus():
    corpus = {e.text.strip().lower() for e in generate(split="all")}
    for folder in ("held_out", "held_out_2", "held_out_3"):
        for path in (CALLERS / folder).glob("*.yml"):
            for turn in yaml.safe_load(path.read_text(encoding="utf-8"))["turns"]:
                text = turn["text"].strip().lower()
                assert len(text.split()) < 4 or text not in corpus, (folder, text)


# ------------------------------------------------------------------ the classifier


def test_inference_matches_the_scikit_learn_pipeline_it_was_exported_from():
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression

    from claimvoice.nlu.train import _export

    data = generate(split="train", scale=0.06)
    vec = TfidfVectorizer(analyzer=features, sublinear_tf=True, min_df=2)
    x = vec.fit_transform([e.text for e in data])
    clf = LogisticRegression(C=4.0, max_iter=2000).fit(x, [e.label for e in data])
    model = LossTypeModel(_export(vec, clf, 1.0, {"accept": 0.9, "confirm": 0.5}))
    for text in ("A pickup clipped my car on Deerfoot.", "Le vent a arraché la clôture.", "Yes, that's fine."):
        want = clf.predict_proba(vec.transform([text]))[0]
        got = model.predict(text).probabilities
        assert np.allclose([got[c] for c in clf.classes_], want, atol=1e-3)


def test_the_committed_model_loads_with_sane_thresholds():
    model = loaded()
    assert model is not None
    assert set(model.labels) == set(lx.LABELS)
    assert 0.0 < model.thresholds["confirm"] <= model.thresholds["accept"] < 1.0
    assert model.temperature > 0


@pytest.mark.parametrize(
    ("text", "label"),
    [
        ("Hey, a delivery van clipped my mirror backing out of the lane.", "collision"),
        ("Water's been seeping in under the baseboards in the rec room.", "water"),
        ("Le grêlon a fissuré mon pare-brise.", "hail"),
        ("Ils ont pris mes outils dans le cabanon.", "theft"),
        ("Yes, go ahead.", "none"),
        ("It's LM-AB-204118.", "none"),
    ],
)
def test_the_model_reads_open_wording(text, label):
    model = loaded()
    assert model is not None
    assert model.predict(text).label == label


def test_inference_is_well_under_five_milliseconds():
    model = loaded()
    assert model is not None
    texts = [e.text for e in generate(split="val", scale=0.05)][:300]
    started = time.perf_counter()
    for t in texts:
        model.predict(t)
    assert (time.perf_counter() - started) * 1000 / len(texts) < 5.0


# ------------------------------------------------------------------ the offline reader


class _Stub:
    """A model that is unsure: 0.6 for wind on anything mentioning the shed, `none` otherwise."""

    thresholds = {"accept": 0.86, "confirm": 0.3}

    def predict(self, text: str) -> Prediction:
        if "shed" in text:
            return Prediction("wind", 0.6, {"wind": 0.6, "none": 0.4}, None)
        return Prediction("none", 0.9, {"none": 0.9}, None)


def test_rules_answer_first_and_the_model_fills_what_they_miss():
    reader = OfflineUnderstanding()
    ruled = reader.understand_sync(request("The hail dented my hood."))
    assert [v.value for v in ruled.slots if v.key == "loss_type"] == ["hail"] and ruled.source == "fake"
    learned = reader.understand_sync(request("Hey, a pickup clipped the side of my car merging onto the ring road."))
    lt = next(v for v in learned.slots if v.key == "loss_type")
    assert lt.value == "collision" and learned.source == "model"
    start, end = lt.span
    assert learned.slots and 0 <= start < end <= len(
        "Hey, a pickup clipped the side of my car merging onto the ring road."
    )


def test_the_model_only_reads_while_what_happened_is_unknown():
    reader = OfflineUnderstanding()
    details = reader.understand_sync(request("A pickup clipped my car.", stage="loss_details"))
    assert not any(v.key == "loss_type" for v in details.slots)
    nothing_asked = reader.understand_sync(request("A pickup clipped my car.", keys=("injury_reported",)))
    assert not any(v.key == "loss_type" for v in nothing_asked.slots)


def test_an_unsure_reading_is_a_candidate_not_a_value():
    reader = OfflineUnderstanding(model=_Stub())  # type: ignore[arg-type]
    r = reader.understand_sync(request("The thing out back, the shed, it's wrecked."))
    assert not any(v.key == "loss_type" for v in r.slots)
    assert [v.value for v in r.candidates] == ["wind"]


async def test_the_line_confirms_an_unsure_loss_type_before_keeping_it():
    reader = OfflineUnderstanding(model=_Stub())  # type: ignore[arg-type]
    lines = ["Hi, the shed out back is a total mess.", *GORD_START[1:], "Everyone's fine, nothing dangerous.", "Yes."]
    result, _ = await call(lines, nlu=reader, hang_up=False)
    said = [o.text for o in result.outs if isinstance(o, Say)]
    assert any("is this about wind damage" in s for s in said)
    assert result.engine.loss_type == "wind" and result.engine.stage is Stage.LOSS_DETAILS
    assert result.engine.slots["loss_type"].turn_id == result.engine.turns[1].turn_id  # points at the opening


async def test_a_no_to_the_confirmation_asks_which_kind_and_is_not_a_miss():
    reader = OfflineUnderstanding(model=_Stub())  # type: ignore[arg-type]
    lines = ["Hi, the shed out back is a total mess.", *GORD_START[1:], "Everyone's fine, nothing dangerous.", "No."]
    result, sink = await call(lines, nlu=reader, hang_up=False)
    assert result.engine.loss_type is None and result.engine.stage is Stage.LOSS_TYPE
    assert result.engine.misses == 0 and not sink.of("handoff")
    assert "collision, wind or hail" in result.engine.last_prompt[1]


# ------------------------------------------------------------------ lexicon-backed extractors


def values(text: str, keys: tuple[str, ...], asked: str | None = None, stage: str = "loss_details") -> dict:
    r = OfflineUnderstanding(use_model=False).understand_sync(request(text, stage=stage, keys=keys, asked=asked))
    return {v.key: v.value for v in r.slots}


@pytest.mark.parametrize(
    ("text", "keys", "asked", "want"),
    [
        ("I'm okay, just a bit sore in the shoulder.", ("injury_reported",), "injury_reported", True),
        ("No, nothing broken.", ("forced_entry",), "forced_entry", False),
        ("Not yet, I'll call them tonight.", ("police_report_filed",), "police_report_filed", False),
        ("The toilet upstairs overflowed.", ("water_source",), "water_source", "other"),
        ("Le chauffe-eau a coulé.", ("water_source",), "water_source", "appliance"),
        ("He's with Aviva, I think.", ("other_party_insurer",), "other_party_insurer", "Aviva"),
        ("Yeah, it's 26-118204.", ("police_report_number",), "police_report_number", "26-118204"),
        ("It had to go on a tow truck.", ("vehicle_drivable",), "vehicle_drivable", False),
        ("That's fine.", ("photos_promised",), "photos_promised", True),
    ],
)
def test_lexicon_backed_extractors(text, keys, asked, want):
    assert values(text, keys, asked).get(keys[0]) == want


def test_one_opening_fills_several_fields_each_with_its_span():
    text = "A van rear-ended me and now the tailgate won't close."
    r = OfflineUnderstanding(use_model=False).understand_sync(
        request(text, stage="loss_details", keys=("other_party_involved", "damage_areas"))
    )
    got = {v.key: v for v in r.slots}
    assert got["other_party_involved"].value is True and "tailgate" in got["damage_areas"].value
    for v in got.values():
        assert text[v.span[0] : v.span[1]].strip()


def test_the_day_before_yesterday():
    assert values("It was the day before yesterday.", ("loss_date",), "loss_date") == {"loss_date": "2026-01-06"}
