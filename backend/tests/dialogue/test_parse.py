from datetime import date, datetime, time

import pytest

from claimvoice.nlu.parse import (
    digit_runs,
    find_date,
    find_money,
    find_phone,
    find_policy_number,
    find_postal,
    find_time,
    money_band,
    spoken_year,
    word_number,
)
from claimvoice.nlu.redaction import REDACTED, contains_card_number, redact_card_numbers

NOW = datetime(2026, 1, 8, 7, 42)
TODAY = NOW.date()


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("I heard a bang around two in the morning.", time(2, 0)),
        ("I'd say around eleven last night.", time(23, 0)),
        ("Hier soir vers neuf heures.", time(21, 0)),
        ("It happened at 5:52 p.m.", time(17, 52)),
        ("About ten past two.", time(2, 10)),
        ("Je l'ai vu ce matin vers six heures.", time(6, 0)),
        ("vers 18 h 30", time(18, 30)),
        ("à huit heures et demie du soir", time(20, 30)),
        ("about twenty minutes ago", time(7, 22)),
        ("around midnight", time(0, 0)),
    ],
)
def test_times_in_english_and_french(text, expected):
    hit = find_time(text, now=NOW)
    assert hit is not None and hit.value == expected


def test_a_correction_keeps_the_half_of_day_it_corrects():
    assert find_time("more like two thirty, not two", now=NOW, prior=time(2, 0)).value == time(2, 30)
    assert find_time("more like four thirty", now=NOW, prior=time(16, 0)).value == time(16, 30)


def test_numbers_that_are_not_times_are_ignored():
    assert find_time("two cars hit me", now=NOW) is None
    assert find_time("about five minutes ago", now=NOW).relative_minutes == 5


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("It was overnight, around two", TODAY),
        ("yesterday afternoon", date(2026, 1, 7)),
        ("last Tuesday", date(2026, 1, 6)),
        ("mardi dernier", date(2026, 1, 6)),
        ("on December 28th", date(2025, 12, 28)),
        ("le 3 janvier", date(2026, 1, 3)),
        ("two days ago", date(2026, 1, 6)),
        ("il y a deux jours", date(2026, 1, 6)),
    ],
)
def test_loss_dates(text, expected):
    hit = find_date(text, today=TODAY, loss_time=time(2, 0) if "two" in text and "overnight" in text else None)
    assert hit is not None and hit.value == expected


def test_dates_of_birth_with_spoken_years():
    assert find_date("March third, 1971.", today=TODAY).value == date(1971, 3, 3)
    assert find_date("the fifth of June nineteen eighty-two", today=TODAY).value == date(1982, 6, 5)
    assert find_date("le trois mars mille neuf cent soixante et onze", today=TODAY).value == date(1971, 3, 3)
    assert spoken_year("nineteen seventy-one") == 1971
    assert word_number("quatre-vingt-deux") == 82


def test_policy_numbers_typed_or_spelled():
    assert find_policy_number("Sure, it's LM-AB-204118.")[0] == "LM-AB-204118"
    assert find_policy_number("It's L-M, A-B, one-eight-seven, three-four-two.")[0] == "LM-AB-187342"
    assert find_policy_number("L M 204118", default_region="CA-AB")[0] == "LM-AB-204118"
    assert find_policy_number("no number here") is None


def test_postal_zip_phone_and_money():
    assert find_postal("Mon code postal est H2G 1T4.")[0] == "H2G 1T4"
    assert find_postal("Zip code is 80206.")[0] == "80206"
    assert find_phone("text me at (403) 555-0142")[0] == "+14035550142"
    assert find_money("maybe five thousand dollars")[0] == 5000
    assert money_band(12000) == "10k_50k"


def test_spoken_digit_runs():
    runs = digit_runs("four-five three two, oh one five one, double two")
    assert [r.digits for r in runs] == ["4532015122"]


@pytest.mark.parametrize(
    "text",
    [
        "my card is 4111 1111 1111 1111",
        "the number is four one one one one one one one one one one one one one one one",
        "Do you need my card for the deductible? It's four-five",
        "Ma carte, c'est quatre cinq trois deux zéro un cinq un",
        "Visa 4111-1111-1111-1111 expiring next year",
    ],
)
def test_card_numbers_are_removed_written_or_spoken(text):
    out = redact_card_numbers(text)
    assert out.count >= 1 and REDACTED in out.text
    assert not contains_card_number(out.text)
    assert not any(w in out.text.lower() for w in ("4111", "four one one one", "quatre cinq"))


def test_policy_phone_and_dates_survive_redaction():
    text = "Policy LM-AB-204118, born March third 1971, call 403-555-0142"
    assert redact_card_numbers(text).text == text
    assert redact_card_numbers("ref 1234 5678 9012 3456").count == 0  # fails Luhn, no card mentioned
