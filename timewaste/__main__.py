"""Command-line entry point: python -m timewaste {userbot,bot,chat,stats}."""

import argparse
import asyncio
import logging

from .brain import make_brain
from .config import Config
from .engine import Engine
from .personas import PERSONAS
from .store import Store, format_stats

LOCAL_CHAT_ID = 0


async def chat_locally(engine: Engine, persona: str) -> None:
    """Play the scammer yourself in the terminal to try out a persona."""
    engine.store.reset(LOCAL_CHAT_ID)
    engine.store.activate(LOCAL_CHAT_ID, persona, "terminal")
    print(f"You are the scammer; {PERSONAS[persona].name} is listening. Ctrl+D to quit.\n")

    async def send(text: str) -> None:
        print(f"{PERSONAS[persona].name}: {text}\n")

    while True:
        try:
            line = await asyncio.to_thread(input, "scammer> ")
        except EOFError:
            break
        if line.strip():
            engine.store.add_message(LOCAL_CHAT_ID, "scammer", line)
            await engine.reply_now(LOCAL_CHAT_ID, send)
    engine.store.reset(LOCAL_CHAT_ID)


def main() -> None:
    parser = argparse.ArgumentParser(prog="timewaste", description=__doc__)
    parser.add_argument(
        "mode",
        choices=["userbot", "bot", "chat", "stats"],
        help="userbot: reply in your own DMs; bot: run a @BotFather bot; "
        "chat: try a persona in the terminal; stats: print totals",
    )
    parser.add_argument("--persona", choices=list(PERSONAS), help="override PERSONA")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    for noisy in ("httpx", "telethon"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    config = Config()
    if args.persona:
        config.persona = args.persona
    if config.persona not in PERSONAS:
        parser.error(f"PERSONA must be one of: {', '.join(PERSONAS)}")
    store = Store(config.db_path)

    if args.mode == "stats":
        print(format_stats(store.stats()))
        return

    engine = Engine(store, make_brain(config.model, config.anthropic_api_key), config.reply_delay)
    if args.mode == "chat":
        asyncio.run(chat_locally(engine, config.persona))
    elif args.mode == "userbot":
        from . import userbot

        userbot.run(config, engine)
    else:
        from . import bot

        bot.run(config, engine)


if __name__ == "__main__":
    main()
