"""Generates the bait's next message from the conversation so far."""

import logging
import random

import anthropic

from .personas import Persona, system_prompt

log = logging.getLogger(__name__)

History = list[tuple[str, str]]  # (role, text) with role in {"scammer", "bait"}


class CannedBrain:
    """Picks a stalling line from the persona's list. Works with no API key."""

    def __init__(self, rng: random.Random | None = None):
        self.rng = rng or random.Random()

    async def reply(self, persona: Persona, history: History) -> str:
        used = {text for role, text in history if role == "bait"}
        fresh = [s for s in persona.stalls if s not in used] or list(persona.stalls)
        return self.rng.choice(fresh).replace("{n}", str(self.rng.randint(1000, 9999)))


def to_messages(history: History) -> list[dict]:
    """Convert stored history into alternating user/assistant API messages."""
    messages: list[dict] = []
    for role, text in history:
        api_role = "user" if role == "scammer" else "assistant"
        if messages and messages[-1]["role"] == api_role:
            messages[-1]["content"] += "\n" + text
        else:
            messages.append({"role": api_role, "content": text})
    # The API needs the conversation to start (and here, end) on a user turn.
    while messages and messages[0]["role"] != "user":
        messages.pop(0)
    while messages and messages[-1]["role"] != "user":
        messages.pop()
    return messages


class ClaudeBrain:
    """Writes in-character replies with Claude, falling back to canned lines."""

    def __init__(self, model: str, api_key: str | None = None, fallback: CannedBrain | None = None):
        self.client = anthropic.AsyncAnthropic(api_key=api_key or None)
        self.model = model
        self.fallback = fallback or CannedBrain()

    async def reply(self, persona: Persona, history: History) -> str:
        messages = to_messages(history)
        if not messages:
            return await self.fallback.reply(persona, history)
        try:
            response = await self.client.beta.messages.create(
                model=self.model,
                max_tokens=16000,
                system=system_prompt(persona),
                messages=messages,
                # Chatty, low-stakes replies: low effort keeps them quick and cheap.
                output_config={"effort": "low"},
                # If a safety classifier declines, let the API retry on its
                # recommended fallback model instead of returning a refusal.
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except anthropic.APIError as exc:
            log.warning("Claude request failed (%s); using a canned reply", exc)
            return await self.fallback.reply(persona, history)

        if response.stop_reason == "refusal":
            log.info("Claude declined to answer; using a canned reply")
            return await self.fallback.reply(persona, history)

        text = "".join(b.text for b in response.content if b.type == "text").strip()
        return text or await self.fallback.reply(persona, history)


def make_brain(model: str, api_key: str) -> ClaudeBrain | CannedBrain:
    if api_key:
        return ClaudeBrain(model, api_key)
    log.warning("ANTHROPIC_API_KEY not set; using canned replies only")
    return CannedBrain()
