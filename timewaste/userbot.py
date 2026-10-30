"""Userbot mode: runs on your own Telegram account and answers scammers in your DMs.

Regular Telegram bots can't see your private chats, so this logs in as you
(via Telethon / MTProto). Controls, typed by you in any private chat:

    .waste [persona]   start wasting this chat's time (message is deleted)
    .unwaste           stop replying in this chat
    .reset             forget this chat's history
    .stats             show totals (sent to your Saved Messages)
"""

import logging
from contextlib import asynccontextmanager

from telethon import TelegramClient, events
from telethon.tl.types import User

from .config import Config
from .detect import looks_like_scam, scam_score
from .engine import Engine
from .personas import PERSONAS
from .store import format_stats

log = logging.getLogger(__name__)

# Telegram's own service account (login codes etc.). Never talk to it.
TELEGRAM_SERVICE_ID = 777000


def _is_stranger(sender) -> bool:
    return (
        isinstance(sender, User)
        and not sender.bot
        and not sender.is_self
        and not sender.contact
        and not sender.verified
        and not sender.support
        and sender.id != TELEGRAM_SERVICE_ID
    )


def _display_name(user: User) -> str:
    name = " ".join(p for p in (user.first_name, user.last_name) if p)
    return f"{name} (@{user.username})" if user.username else name


def build_client(config: Config, engine: Engine) -> TelegramClient:
    if not (config.api_id and config.api_hash):
        raise SystemExit("Userbot mode needs TG_API_ID and TG_API_HASH (see .env.example)")

    client = TelegramClient(config.session_name, config.api_id, config.api_hash)
    store = engine.store

    def transport(chat_id: int):
        async def send(text: str) -> None:
            await client.send_message(chat_id, text)

        @asynccontextmanager
        async def typing():
            await client.send_read_acknowledge(chat_id)
            async with client.action(chat_id, "typing"):
                yield

        return send, typing

    @client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
    async def on_incoming(event: events.NewMessage.Event) -> None:
        sender = await event.get_sender()
        if not _is_stranger(sender):
            return
        text = event.raw_text or "[sent an attachment]"
        chat = store.get_chat(event.chat_id)

        if chat is None and config.auto_engage and looks_like_scam(text, config.scam_threshold):
            log.info("Auto-engaging %s (score %d)", _display_name(sender), scam_score(text))
            store.activate(event.chat_id, config.persona, _display_name(sender))
            chat = store.get_chat(event.chat_id)

        if chat is None or not chat.active:
            return
        log.info("chat %s -> %s", event.chat_id, text)
        engine.on_scammer_message(event.chat_id, text, *transport(event.chat_id))

    @client.on(events.NewMessage(outgoing=True, pattern=r"^\.(waste|unwaste|reset|stats)\b\s*(\w*)"))
    async def on_command(event: events.NewMessage.Event) -> None:
        command, arg = event.pattern_match.group(1), event.pattern_match.group(2).lower()
        await event.delete()

        if command == "stats":
            await client.send_message("me", "timewaste stats\n" + format_stats(store.stats()))
            return
        if not event.is_private:
            await client.send_message("me", "timewaste only works in private chats.")
            return

        if command == "waste":
            persona = arg or config.persona
            if persona not in PERSONAS:
                await client.send_message("me", f"Unknown persona {persona!r}. Options: {', '.join(PERSONAS)}")
                return
            peer = await event.get_chat()
            store.activate(event.chat_id, persona, _display_name(peer) if isinstance(peer, User) else "")
            log.info("Manually engaged chat %s as %s", event.chat_id, persona)
            # If they already wrote something, answer it as if it just arrived.
            last = await client.get_messages(event.chat_id, limit=1, from_user=event.chat_id)
            if last and last[0].raw_text and not store.history(event.chat_id):
                engine.on_scammer_message(event.chat_id, last[0].raw_text, *transport(event.chat_id))
        elif command == "unwaste":
            engine.stop(event.chat_id)
        elif command == "reset":
            engine.stop(event.chat_id)
            store.reset(event.chat_id)

    return client


def run(config: Config, engine: Engine) -> None:
    client = build_client(config, engine)
    if config.phone:
        client.start(phone=config.phone)
    else:
        client.start()
    log.info(
        "Userbot running (auto-engage %s). Type .waste in a chat to start.",
        "on" if config.auto_engage else "off",
    )
    client.run_until_disconnected()
