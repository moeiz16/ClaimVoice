import asyncio
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import msgspec

from claimvoice.contracts import CallSink, MemoryCallSink
from claimvoice.nlu.base import Intent, LanguageUnderstanding, LlmClient, NluRequest
from claimvoice.nlu.fake import FakeLlm, FakeUnderstanding
from claimvoice.nlu.redaction import REDACTED, redact_card_numbers
from claimvoice.schemas import voice
from claimvoice.tools.base import run_tool
from claimvoice.tools.sms import FakeSms, SmsSender
from claimvoice.tools.weather import BundledWeather, WeatherFeed
from claimvoice.voice.adapters import FakeSpeechToText, FakeTextToSpeech, SpeechToText, TextToSpeech


def test_fakes_satisfy_their_protocols():
    assert isinstance(FakeSpeechToText(), SpeechToText)
    assert isinstance(FakeTextToSpeech(), TextToSpeech)
    assert isinstance(FakeUnderstanding(), LanguageUnderstanding)
    assert isinstance(FakeLlm(), LlmClient)
    assert isinstance(FakeSms(), SmsSender)
    assert isinstance(BundledWeather(date(2026, 1, 8)), WeatherFeed)
    assert isinstance(MemoryCallSink(), CallSink)


async def test_fake_stt_plays_its_script_then_returns_silence():
    stt = FakeSpeechToText()
    stt.queue(["My car was hit by hail"], language="en")
    first = await stt.transcribe(b"", sample_rate=16000, language="en")
    second = await stt.transcribe(b"", sample_rate=16000, language="en")
    assert first.text == "My car was hit by hail" and second.text == "" and second.confidence == 0.0


async def test_fake_tts_streams_20ms_chunks():
    tts = FakeTextToSpeech()
    chunks = [c async for c in tts.synthesize("Bonjour", language="fr")]
    assert chunks and all(len(c) == tts.sample_rate // 50 * 2 for c in chunks)


async def test_fake_nlu_catches_handoff_and_safety_in_both_languages():
    nlu = FakeUnderstanding()
    ask = await nlu.understand(
        NluRequest(stage="identity", utterance="Can I talk to a person please", language="en", expecting=())
    )
    assert ask.intent is Intent.HANDOFF_REQUEST
    gas = await nlu.understand(
        NluRequest(
            stage="loss_details", utterance="Il y a une odeur de gaz dans le sous-sol", language="fr", expecting=()
        )
    )
    assert gas.urgent_safety


def test_card_numbers_are_removed_but_policy_and_phone_numbers_are_kept():
    text = "my card is 4111 1111 1111 1111 and policy LM-AB-204118, call me at 403-555-0142"
    out = redact_card_numbers(text)
    assert out.count == 1
    assert "4111" not in out.text and REDACTED in out.text
    assert "LM-AB-204118" in out.text and "403-555-0142" in out.text
    assert redact_card_numbers("ref 1234 5678 9012 3456").count == 0  # fails the Luhn check


async def test_tool_runner_times_out_with_fallback():
    async def slow():
        await asyncio.sleep(1)
        return "late"

    value, timing = await run_tool("policy_lookup", slow, fallback="fallback", budget_ms=50)
    assert value == "fallback" and timing.timed_out and timing.elapsed_ms < 500


async def test_bundled_weather_confirms_the_calgary_chinook_on_the_demo_morning():
    feed = BundledWeather(date(2026, 1, 8))
    morning = datetime(2026, 1, 8, 7, 42, tzinfo=ZoneInfo("America/Edmonton"))
    alerts = await feed.alerts("CA-AB", morning)
    assert [a.kind for a in alerts] == ["wind"]
    near = await feed.events_near(51.12, -113.95, morning + timedelta(days=1))  # Saddle Ridge, reported next day
    assert any(a.kind == "wind" for a in near)
    assert not await feed.alerts("CA-AB", morning + timedelta(days=3))


async def test_fake_sms_masks_the_number():
    sms = FakeSms()
    receipt = await sms.send("+14035550142", "Add photos: https://x/p/abc", org_id="o1", call_id="c1")
    assert receipt.to_masked.endswith("0142") and "403" not in receipt.to_masked
    assert len(sms.for_call("c1")) == 1


def test_data_channel_messages_round_trip():
    raw = b'{"type":"caller.text","text":"oui","final":true,"language":"fr","endedAtMs":1200}'
    msg = voice.client_decoder.decode(raw)
    assert isinstance(msg, voice.CallerText) and msg.ended_at_ms == 1200
    out = msgspec.json.encode(voice.LineStop(turn_id="t9", reason="barge_in"))
    assert out == b'{"type":"line.stop","turnId":"t9","reason":"barge_in"}'
