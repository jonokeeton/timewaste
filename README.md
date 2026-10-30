# timewaste

A Telegram bot that replies to scam messages in character and keeps scammers busy for as long as possible. Every minute they spend on a confused retiree who can't find his bank card is a minute they aren't spending on a real victim.

Replies are written by Claude, playing one of several personas. If no API key is set, the bot falls back to a list of canned stalling lines.

## Personas

| Key | Character |
| --- | --- |
| `gerald` (default) | 79-year-old retired railway signalman. Polite, a bit deaf, baffled by his phone, loves train stories. |
| `brenda` | Over-enthusiastic candle-business owner. Gets distracted by her kids, her book club and her candles. |
| `dave` | Painfully procedural IT helpdesk worker. Wants a ticket number and manager sign-off for everything. |

The personas never share real data. They invent fake details or "go and look for" them, never say money was actually sent, and never follow links. To add a persona, add an entry to `timewaste/personas.py`.

## Two ways to run it

### 1. Userbot: replies in your own DMs (recommended)

A regular Telegram bot can't read your private chats, and scammers message *you*, not a bot. Userbot mode logs in as your own account using [Telethon](https://docs.telethon.dev) and replies from it.

Type these commands in any private chat. The command message is deleted right away, so the scammer never sees it:

| Command | Effect |
| --- | --- |
| `.waste [persona]` | Start replying in this chat. If they already wrote something, the bot answers it. |
| `.unwaste` | Stop replying in this chat. |
| `.reset` | Stop, and forget this chat's history. |
| `.stats` | Send totals to your Saved Messages. |

With `AUTO_ENGAGE=true`, the bot also starts on its own when someone who **isn't in your contacts** sends a message that looks like a scam: crypto or investment pitches, "you've won", job offers, gift cards, and so on (see `timewaste/detect.py`). It never replies to contacts, bots, verified accounts or Telegram's own service messages.

> Automating a user account is allowed by Telegram's API terms, but sending lots of messages from it can get the account limited. The default reply delay (20 to 120 seconds, plus a believable typing time) keeps the volume low and looks human. Consider using a spare account.

### 2. Bot mode: a normal @BotFather bot

- **Bait:** anyone who messages the bot except you is treated as a scammer and strung along. Give scammers its username ("I'm busy, talk to my assistant @...").
- **Copilot for you:** forward or paste a scammer's message to the bot and it replies with what to send next. `/new [persona]` starts a fresh conversation and `/stats` shows totals.

## Setup

```bash
git clone https://github.com/jonokeeton/timewaste && cd timewaste
```

```bash
python3 -m venv .venv && . .venv/bin/activate
```

```bash
pip install -r requirements.txt
```

```bash
cp .env.example .env
```

Then fill in `.env`:

- `ANTHROPIC_API_KEY`: from <https://platform.claude.com>. Optional, but replies are much better with it.
- Userbot: `TG_API_ID` and `TG_API_HASH` from <https://my.telegram.org> → *API development tools*, plus `TG_PHONE`.
- Bot: `TG_BOT_TOKEN` from [@BotFather](https://t.me/BotFather), and `OWNER_ID` (your numeric user id; [@userinfobot](https://t.me/userinfobot) will tell you).

Run it:

```bash
python -m timewaste userbot
```

```bash
python -m timewaste bot
```

On the first userbot run, Telegram sends you a login code. The session is saved to `timewaste.session`, which gives full access to your account, so keep it private (it's in `.gitignore`).

### Try a persona without Telegram

```bash
python -m timewaste chat --persona brenda
```

You play the scammer in the terminal.

### Other settings

| Variable | Default | Meaning |
| --- | --- | --- |
| `PERSONA` | `gerald` | Default persona |
| `MODEL` | `claude-opus-5-5` | Claude model used for replies |
| `REPLY_DELAY` | `20,120` | Random wait before replying, in seconds. Messages that arrive during the wait are answered together. |
| `AUTO_ENGAGE` | `false` | Userbot: engage strangers whose message looks like a scam |
| `SCAM_THRESHOLD` | `3` | Score needed to auto-engage |
| `DB_PATH` | `timewaste.db` | SQLite file holding conversations and stats |

`python -m timewaste stats` prints how many scammers you've engaged and how much of their time you've wasted.

## Development

```bash
pip install pytest pytest-asyncio && python -m pytest
```
