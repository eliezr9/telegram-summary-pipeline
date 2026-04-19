# Telegram Summary Pipeline

A lightweight pipeline that collects text updates from selected Telegram chats using a **user account**, builds a daily combined batch, summarizes it with **Google Gemini**, and posts the result back to a Telegram destination channel.

This project is designed to be **generic and modular**:
- it is **not limited to war/news topics**
- it can summarize any set of Telegram channels/groups you choose
- you can customize the summary prompt and topic focus easily

## Features

- Uses a **Telegram user account** (not a bot), so it can read chats a bot cannot access
- Keeps **text only** (message text or captions)
- Ignores common noise such as:
  - comment counters
  - repeated channel signature lines
  - Telegram links
  - some repetitive call-to-action lines
- Builds a **daily combined batch**
- Generates a **concise Hebrew summary**
- Retries Gemini generation automatically on failure
- Sends the summary to a Telegram destination channel
- Deletes local batch data after successful delivery
- Can be scheduled daily using `systemd`

---

## Project files

Current repository structure:

- `collect_messages.py` — collect messages from selected chats into SQLite
- `build_combined_batch.py` — build a combined daily input batch
- `summarize_and_send.py` — summarize with Gemini and send to Telegram
- `storage_setup.py` — initialize the SQLite database
- `run_daily_pipeline.sh` — run the full daily pipeline
- `target_chats.example.txt` — example target chats file
- `telegram-summary.service` — example `systemd` service
- `telegram-summary.timer` — example `systemd` timer
- `.env.example` — example environment file

---

## Requirements

- Python 3.11+
- A Telegram account
- Telegram API credentials (`API_ID`, `API_HASH`)
- A Gemini API key

Install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
