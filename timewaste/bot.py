"""Bot mode: a regular @BotFather bot.

- Anyone who isn't the owner is treated as a scammer and gets baited directly.
  Hand the bot's @username to scammers ("message my assistant, I'm busy").
- The owner gets a copilot: forward or paste a scam message and the bot
  suggests the next reply to send from your own account.
"""

import asyncio
import contextlib
import logging

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from .config import Config
from .engine import Engine
from .personas import PERSONAS
from .store import format_stats

log = logging.getLogger(__name__)

HELP = (
    "Forward or paste a scammer's message and I'll write the next reply for you.\n\n"
    "/new [persona] start a fresh conversation ({personas})\n"
    "/stats how much scammer time has been wasted"
)


def build_app(config: Config, engine: Engine) -> Application:
    if not config.bot_token:
        raise SystemExit("Bot mode needs TG_BOT_TOKEN (see .env.example)")
    store = engine.store
    app = Application.builder().token(config.bot_token).build()

    def is_owner(update: Update) -> bool:
        return config.owner_id is not None and update.effective_user.id == config.owner_id

    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if is_owner(update):
            await update.message.reply_text(HELP.format(personas=", ".join(PERSONAS)))
        else:
            # A scammer opening the bot: treat it like any other first message.
            await on_text(update, context)

    async def new(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not is_owner(update):
            return
        persona = (context.args[0].lower() if context.args else config.persona)
        if persona not in PERSONAS:
            await update.message.reply_text(f"Unknown persona. Options: {', '.join(PERSONAS)}")
            return
        store.reset(update.effective_chat.id)
        store.activate(update.effective_chat.id, persona, "copilot")
        await update.message.reply_text(f"New conversation as {PERSONAS[persona].name}. Forward me their message.")

    async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if is_owner(update):
            await update.message.reply_text(format_stats(store.stats()))

    async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.message
        chat_id = update.effective_chat.id
        text = message.text or message.caption or "[sent an attachment]"

        if is_owner(update):
            # Copilot: answer straight away, no human-like delay.
            if store.get_chat(chat_id) is None:
                store.activate(chat_id, config.persona, "copilot")
            store.add_message(chat_id, "scammer", text)
            await context.bot.send_chat_action(chat_id, ChatAction.TYPING)
            await engine.reply_now(chat_id, message.reply_text)
            return

        # Everyone else is fair game.
        if store.get_chat(chat_id) is None:
            user = update.effective_user
            store.activate(chat_id, config.persona, user.full_name)

        async def send(reply: str) -> None:
            await context.bot.send_message(chat_id, reply)

        engine.on_scammer_message(chat_id, text, send, lambda: _Typing(context, chat_id))

    private = filters.ChatType.PRIVATE
    app.add_handler(CommandHandler("start", start, filters=private))
    app.add_handler(CommandHandler("new", new, filters=private))
    app.add_handler(CommandHandler("stats", stats, filters=private))
    app.add_handler(MessageHandler(private & ~filters.COMMAND, on_text))
    return app


class _Typing:
    """Keeps "typing..." visible; Telegram clears each chat action after ~5s."""

    def __init__(self, context: ContextTypes.DEFAULT_TYPE, chat_id: int):
        self.context, self.chat_id = context, chat_id
        self._task: asyncio.Task | None = None

    async def _loop(self) -> None:
        while True:
            await self.context.bot.send_chat_action(self.chat_id, ChatAction.TYPING)
            await asyncio.sleep(4)

    async def __aenter__(self):
        self._task = asyncio.create_task(self._loop())

    async def __aexit__(self, *exc):
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        return False


def run(config: Config, engine: Engine) -> None:
    if config.owner_id is None:
        log.warning("OWNER_ID not set: every user will be treated as a scammer")
    app = build_app(config, engine)
    log.info("Bot running")
    app.run_polling(allowed_updates=[Update.MESSAGE])
