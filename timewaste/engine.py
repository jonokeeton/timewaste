"""Transport-agnostic reply loop shared by the userbot and the Bot API bot.

When a scammer writes, we wait a random while (so bursts of messages get a
single reply and we look like a slow human), then "type" for a believable
amount of time and send the next in-character message.
"""

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager

from .brain import CannedBrain, ClaudeBrain
from .personas import get_persona
from .store import Store

log = logging.getLogger(__name__)

Send = Callable[[str], Awaitable[None]]
Typing = Callable[[], AbstractAsyncContextManager]

# Seconds of "typing" per character, capped so replies don't take forever.
TYPING_SPEED = 0.12
MAX_TYPING = 45.0


class Engine:
    def __init__(
        self,
        store: Store,
        brain: ClaudeBrain | CannedBrain,
        reply_delay: tuple[float, float],
        rng: random.Random | None = None,
        typing_speed: float = TYPING_SPEED,
    ):
        self.store = store
        self.brain = brain
        self.reply_delay = reply_delay
        self.rng = rng or random.Random()
        self.typing_speed = typing_speed
        self._waiting: dict[int, asyncio.Task] = {}
        self._locks: dict[int, asyncio.Lock] = {}

    def on_scammer_message(self, chat_id: int, text: str, send: Send, typing: Typing) -> None:
        """Record a message from an active chat and schedule a reply."""
        self.store.add_message(chat_id, "scammer", text)
        # Another message arrived while we were still "away": restart the wait
        # so one reply covers the whole burst.
        pending = self._waiting.pop(chat_id, None)
        if pending is not None:
            pending.cancel()
        self._waiting[chat_id] = asyncio.create_task(self._reply_later(chat_id, send, typing))

    async def _reply_later(self, chat_id: int, send: Send, typing: Typing) -> None:
        try:
            await asyncio.sleep(self.rng.uniform(*self.reply_delay))
        except asyncio.CancelledError:
            return
        if self._waiting.get(chat_id) is asyncio.current_task():
            del self._waiting[chat_id]
        lock = self._locks.setdefault(chat_id, asyncio.Lock())
        async with lock:
            try:
                await self.reply_now(chat_id, send, typing)
            except Exception:
                log.exception("Failed to reply in chat %s", chat_id)

    async def reply_now(self, chat_id: int, send: Send, typing: Typing | None = None) -> str | None:
        chat = self.store.get_chat(chat_id)
        if chat is None or not chat.active:
            return None
        history = self.store.history(chat_id)
        if not history or history[-1][0] != "scammer":
            return None
        text = await self.brain.reply(get_persona(chat.persona), history)
        if typing is not None:
            async with typing():
                await asyncio.sleep(min(len(text) * self.typing_speed, MAX_TYPING))
        await send(text)
        self.store.add_message(chat_id, "bait", text)
        log.info("chat %s <- %s", chat_id, text)
        return text

    def stop(self, chat_id: int) -> None:
        pending = self._waiting.pop(chat_id, None)
        if pending is not None:
            pending.cancel()
        self.store.deactivate(chat_id)
