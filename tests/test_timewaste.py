import asyncio
import contextlib
import random

from timewaste.brain import CannedBrain, to_messages
from timewaste.detect import looks_like_scam, scam_score
from timewaste.engine import Engine
from timewaste.personas import PERSONAS
from timewaste.store import Store, format_duration


def test_detects_common_scam_openers():
    assert looks_like_scam("Hello dear, I can help you earn $5000 weekly with crypto trading")
    assert looks_like_scam("Congratulations! You have won a prize, send the fee to claim")
    assert looks_like_scam("We are hiring for a remote job, daily income guaranteed, contact on WhatsApp")


def test_ignores_normal_messages():
    assert scam_score("hey are we still on for lunch tomorrow?") == 0
    assert not looks_like_scam("Can you send me the photos from the trip?")


def test_to_messages_alternates_and_trims():
    history = [
        ("bait", "hello?"),
        ("scammer", "hi"),
        ("scammer", "invest now"),
        ("bait", "how?"),
        ("scammer", "send btc"),
        ("bait", "unsent draft"),
    ]
    assert to_messages(history) == [
        {"role": "user", "content": "hi\ninvest now"},
        {"role": "assistant", "content": "how?"},
        {"role": "user", "content": "send btc"},
    ]


async def test_canned_brain_avoids_repeats():
    persona = PERSONAS["gerald"]
    brain = CannedBrain(random.Random(1))
    history = [("bait", line) for line in persona.stalls[:-1]] + [("scammer", "hi")]
    assert await brain.reply(persona, history) == persona.stalls[-1]


def test_store_stats(tmp_path):
    store = Store(str(tmp_path / "t.db"))
    store.activate(1, "gerald")
    store.add_message(1, "scammer", "hi")
    store.add_message(1, "bait", "who is this")
    stats = store.stats()
    assert (stats.chats, stats.scammer_messages, stats.bait_messages) == (1, 1, 1)
    store.deactivate(1)
    assert not store.get_chat(1).active
    store.reset(1)
    assert store.get_chat(1) is None and store.history(1) == []


def test_format_duration():
    assert format_duration(42) == "42s"
    assert format_duration(3 * 3600 + 120) == "3h 2m"


async def test_engine_batches_bursts_into_one_reply(tmp_path):
    store = Store(str(tmp_path / "t.db"))
    store.activate(7, "brenda")
    engine = Engine(store, CannedBrain(random.Random(0)), reply_delay=(0.05, 0.05), typing_speed=0)
    sent = []

    async def send(text):
        sent.append(text)

    @contextlib.asynccontextmanager
    async def typing():
        yield

    engine.on_scammer_message(7, "hello", send, typing)
    engine.on_scammer_message(7, "are you there", send, typing)
    engine.on_scammer_message(7, "reply fast", send, typing)
    await asyncio.sleep(0.3)

    assert len(sent) == 1
    assert [r for r, _ in store.history(7)] == ["scammer"] * 3 + ["bait"]


async def test_engine_ignores_inactive_chats(tmp_path):
    store = Store(str(tmp_path / "t.db"))
    store.activate(9, "dave")
    engine = Engine(store, CannedBrain(), reply_delay=(0, 0))
    engine.stop(9)
    store.add_message(9, "scammer", "hi")

    async def send(text):
        raise AssertionError("should not send")

    assert await engine.reply_now(9, send) is None
