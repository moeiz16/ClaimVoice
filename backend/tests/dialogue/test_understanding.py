from datetime import datetime

import pytest

from claimvoice.dialogue.slots import SLOT_CATALOG
from claimvoice.nlu.base import Intent, NluRequest, SlotSpec
from claimvoice.nlu.fake import FakeUnderstanding, classify_intent, detect_language, distress_score, urgent_safety

NOW = datetime(2026, 1, 8, 7, 42)
NLU = FakeUnderstanding()


def understand(text, keys=(), asked=None, filled=None, language="en"):
    specs = [SlotSpec(k, SLOT_CATALOG[k].kind if k in SLOT_CATALOG else "text") for k in keys]
    return NLU.understand_sync(
        NluRequest(
            stage="x", utterance=text, language=language, expecting=specs, asked=asked, now=NOW, filled=filled or {}
        )
    )


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("I smell gas, the wind tore the cover off my meter", "gas"),
        ("Ça sent le gaz dans le sous-sol", "gas"),
        ("The kitchen is on fire!", "fire"),
        ("My husband is unconscious", "injury"),
        ("There's water touching the electrical panel", "water_power"),
        ("A power line came down on the car", "power_line"),
        ("My son is trapped in the car", "trapped"),
    ],
)
def test_urgent_safety_words(text, reason):
    hit = urgent_safety(text)
    assert hit is not None and hit[0] == reason


@pytest.mark.parametrize(
    "text",
    [
        "Everyone's okay. Nobody's hurt and nothing's dangerous, the power's still on.",
        "Le panneau électrique est en haut, l'eau ne s'en approche pas.",
        "There's no smell of gas and no smoke.",
        "We had a small kitchen fire last night but it's out now.",
    ],
)
def test_calm_answers_are_not_alarms(text):
    assert urgent_safety(text) is None


def test_distress_is_read_from_words_only():
    assert distress_score("I can't cope with this, I'm falling apart") >= 0.7
    assert 0.3 < distress_score("I'm a bit scared to be honest") < 0.7
    assert distress_score("The bumper is dented") == 0.0


@pytest.mark.parametrize(
    ("text", "intent"),
    [
        ("Can I talk to a real person please", Intent.HANDOFF_REQUEST),
        ("Je veux parler à quelqu'un", Intent.HANDOFF_REQUEST),
        ("Sorry, it was more like two thirty, not two.", Intent.CORRECTION),
        ("Non, c'était mardi, pas lundi.", Intent.CORRECTION),
        ("Could you repeat that?", Intent.REPEAT),
        ("Yes, that's fine.", Intent.AFFIRM),
        ("Oui, j'accepte.", Intent.AFFIRM),
        ("No, I don't want to be recorded.", Intent.DENY),
        ("Will my rates go up?", Intent.OFF_SCRIPT),
        ("No, that's everything. Thank you.", Intent.DENY),
    ],
)
def test_intents(text, intent):
    assert classify_intent(text)[0] is intent


def test_off_script_topics_get_fixed_answers():
    assert classify_intent("Are you a robot?")[1] == "robot"
    assert classify_intent("Is this covered?")[1] == "covered"
    assert classify_intent("Can I use my own contractor?")[1] == "contractor"


def test_language_detection():
    assert detect_language("Bonjour, un tuyau a éclaté et mon sous-sol est inondé.") == "fr"
    assert detect_language("Hi, the wind last night tore up my house.") == "en"
    assert detect_language("ok") is None


def test_values_carry_the_span_they_were_heard_in():
    text = "A pickup hit me from behind. The other driver gave me his insurance, it's with Front Range Auto."
    r = understand(text, ["other_party_involved", "other_party_insurer"], asked="other_party_involved")
    got = {v.key: v for v in r.slots}
    assert got["other_party_involved"].value is True
    assert text[slice(*got["other_party_insurer"].span)] == "Front Range Auto"


def test_a_passing_mention_never_overwrites_but_a_correction_does():
    filled = {"loss_time": "02:00", "loss_date": "2026-01-08"}
    keys = ["loss_time", "loss_date"]
    passing = understand("The neighbour came by at three to help.", keys, asked="home_livable", filled=filled)
    assert not [v for v in passing.slots if v.key == "loss_time"]
    fix = understand("Sorry, it was more like two thirty, not two.", keys, asked="home_livable", filled=filled)
    v = next(v for v in fix.slots if v.key == "loss_time")
    assert v.value == "02:30" and v.corrects


def test_situation_values_update_without_a_correction():
    r = understand(
        "I taped a tarp over the skylight.",
        ["open_to_weather", "mitigation_taken"],
        asked="mitigation_taken",
        filled={"open_to_weather": True},
    )
    assert {v.key: v.value for v in r.slots} == {"open_to_weather": False, "mitigation_taken": True}


def test_french_property_values():
    r = understand(
        "J'ai fermé l'entrée d'eau principale, l'eau n'entre plus.",
        ["water_still_entering", "mitigation_taken"],
        asked="water_still_entering",
        language="fr",
    )
    assert {v.key: v.value for v in r.slots} == {"water_still_entering": False, "mitigation_taken": True}


def test_a_bare_yes_answers_the_asked_question_only():
    r = understand("Yes.", ["home_livable", "vehicle_drivable"], asked="home_livable")
    assert {v.key: v.value for v in r.slots} == {"home_livable": True}


class _ScriptedLlm:
    name = "scripted"

    def __init__(self, reply: str, delay: float = 0.0) -> None:
        self.reply, self.delay = reply, delay

    async def complete(self, system, user, *, json_schema=None, timeout_ms=600, temperature=0.0):
        import asyncio

        await asyncio.sleep(self.delay)
        return self.reply


async def test_cloud_reader_values_are_checked_against_the_words_said():
    import json

    from claimvoice.nlu.llm import LlmUnderstanding

    reply = json.dumps(
        {
            "intent": "answer",
            "values": [
                {"key": "debris_source", "value": "the neighbour's trampoline", "quote": "neighbour's trampoline"},
                {"key": "home_livable", "value": True, "quote": "words never said"},
                {"key": "not_expected", "value": 1, "quote": "trampoline"},
            ],
        }
    )
    reader = LlmUnderstanding(_ScriptedLlm(reply))
    text = "It was the neighbour's trampoline that flew over."
    r = await reader.understand(
        NluRequest(
            stage="loss_details",
            utterance=text,
            language="en",
            now=NOW,
            expecting=[SlotSpec("debris_source", "text"), SlotSpec("home_livable", "yes_no")],
        )
    )
    got = {v.key: v for v in r.slots}
    assert r.source == "llm" and set(got) == {"debris_source"}
    assert text[slice(*got["debris_source"].span)] == "neighbour's trampoline"


async def test_cloud_reader_timeout_falls_back_to_the_rules():
    from claimvoice.nlu.llm import LlmUnderstanding

    reader = LlmUnderstanding(_ScriptedLlm("{}", delay=1.0), timeout_ms=50)
    r = await reader.understand(NluRequest(stage="safety", utterance="I smell gas", language="en", expecting=()))
    assert r.source == "fake" and r.urgent_safety


@pytest.mark.parametrize(
    "text",
    [
        "Somebody dinged my car in the parking lot and drove away.",
        "Another car hit me while I was parked.",
        "It was a hit and run on 17th Avenue.",
        "Quelqu'un a reculé dans ma voiture au centre commercial.",
        "Un autobus a heurté mon auto.",
    ],
)
def test_more_ways_to_describe_a_collision(text):
    r = understand(text, ["loss_type"], asked="loss_type")
    assert {v.key: v.value for v in r.slots}.get("loss_type") == "collision"


def test_the_home_is_fine_and_a_bare_please_is_a_yes():
    r = understand("Oh yes, we're fine in the house.", ["home_livable"], asked="home_livable")
    assert {v.key: v.value for v in r.slots}["home_livable"] is True
    r = understand("Please.", ["photos_promised"], asked="photos_promised")
    assert {v.key: v.value for v in r.slots}["photos_promised"] is True


def test_a_clear_no_police_corrects_a_hurried_yes():
    r = understand(
        "No, I haven't called the police yet.",
        ["police_report_filed", "police_report_number"],
        asked="police_report_number",
        filled={"police_report_filed": True},
    )
    assert {v.key: v.value for v in r.slots}["police_report_filed"] is False
