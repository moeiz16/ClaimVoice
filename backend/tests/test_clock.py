from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from claimvoice import clock


def test_real_time_by_default():
    assert not clock.is_shifted()
    assert abs((clock.now() - datetime.now(UTC)).total_seconds()) < 2


def test_demo_day_shifts_today_by_whole_days():
    clock.install("2026-01-08")
    assert clock.today() == date(2026, 1, 8)
    assert clock.offset().seconds == 0 and clock.offset().microseconds == 0  # whole days; time of day keeps running


def test_pinned_time_of_day_uses_shared_anchor(tmp_path):
    anchor = tmp_path / "demo-clock.json"
    clock.install("2026-01-08", "09:40", tz="America/Edmonton", anchor_file=anchor)
    first = clock.now()
    local = first.astimezone(ZoneInfo("America/Edmonton"))
    assert (local.date(), local.hour, local.minute) == (date(2026, 1, 8), 9, 40)
    # a second process reading the same anchor agrees to within the time elapsed
    clock.uninstall()
    clock.install("2026-01-08", "09:40", tz="America/Edmonton", anchor_file=anchor)
    assert abs((clock.now() - first).total_seconds()) < 2


def test_travel_restores_offset():
    clock.install("2026-01-08")
    before = clock.offset()
    with clock.travel(datetime(2025, 12, 15, 18, 0, tzinfo=UTC)):
        assert clock.today() == date(2025, 12, 15)
    assert clock.offset() == before


def test_header_value_is_iso_utc():
    clock.install("2026-01-08")
    value = clock.header_value()
    assert value[:10] in {"2026-01-07", "2026-01-08", "2026-01-09"}  # UTC date can differ from the local day
    assert value.endswith("+00:00")
