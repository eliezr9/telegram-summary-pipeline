# Telegram Summary Pipeline

A local Python pipeline that reads messages from selected Telegram channels/groups using **your own Telegram user account**, cleans noisy text, builds a combined daily batch, summarizes it with Gemini, and sends the result to a private Telegram channel.

## What it does

- Reads text/captions from selected Telegram sources
- Ignores media-only messages
- Removes common noise such as comment counters and Telegram links
- Builds one combined daily digest window
- Generates a short Hebrew summary with Gemini
- Sends the summary to a private Telegram destination channel
- Cleans local temporary data after a successful send

## Requirements

- Python 3.11+
- A Telegram account
- Telegram `api_id` and `api_hash`
- Gemini API key
- Linux/macOS shell for the included pipeline script

## 1. Create a Telegram API app

1. Log in with your Telegram account.
2. Open `my.telegram.org`.
3. Go to **API development tools**.
4. Create an application.
5. Copy your `api_id` and `api_hash`.

### App naming tip

Use a simple app name with Latin letters only. A short letters-only name is the safest choice if Telegram rejects other formats.

## 2. Create a Gemini API key

1. Open Google AI Studio.
2. Create an API key.
3. Copy it.
4. Keep it private.

## 3. Prepare the project

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app/storage_setup.py
```

## 4. Configure secrets

Copy `.env.example` to `.env` and fill it in:

```bash
cp .env.example .env
```

Set these values:

- `API_ID`
- `API_HASH`
- `SESSION_NAME`
- `SUMMARY_CHANNEL_ID`
- `GEMINI_API_KEY`
- `PRIORITY_CHAT_ID` (optional)
- `SUMMARY_TITLE`
- `SUMMARY_TOPIC`
- `IMPORTANT_ENTITIES` (optional)

## 5. Choose your sources

Copy the example target list:

```bash
cp data/target_chats.example.txt data/target_chats.txt
```

Put **one Telegram chat/channel ID per line** inside `data/target_chats.txt`.

## 6. Find your chat IDs

A simple way is to temporarily write a small script using Pyrogram that logs in and prints your dialogs and IDs, or reuse your existing login test script locally.

## 7. Create a private destination channel

Create a **private Telegram channel** where only you can post.
Use its channel ID as `SUMMARY_CHANNEL_ID`.

## 8. First login

The first Pyrogram run will ask for:

- your phone number
- your Telegram login code
- possibly your 2FA password

This creates a local session file under `data/`.

## 9. Run manually

```bash
source .venv/bin/activate
python app/collect_messages.py
python app/summarize_and_send.py
```

## 10. How the daily window works

The daily summary window is:

- previous day `22:00:00`
- through current day `22:00:00`

The scripts treat that as one summary window.

## 11. Customizing the prompt

Edit `app/summarize_and_send.py`.

The main places to customize are:

- `build_prompt()`
- `build_compression_prompt()`

You can change:

- summary language
- tone/style
- title
- how many bullets to keep
- whether to include direct quotes
- what entities to prioritize

### Recommended modular approach

Keep the code generic and drive behavior mainly through:

- `SUMMARY_TITLE`
- `SUMMARY_TOPIC`
- `IMPORTANT_ENTITIES`
- `PRIORITY_CHAT_ID`

## 12. Optional automation with systemd

Example files are in `deploy/systemd/`.
Adjust paths and usernames before using them.

## 13. Security notes

Never commit:

- `.env`
- `data/*.db`
- `data/*.session*`
- `logs/*`

The provided `.gitignore` already excludes these.

## 14. GitHub publishing

Recommended files to include:

- `app/collect_messages.py`
- `app/build_combined_batch.py`
- `app/storage_setup.py`
- `app/summarize_and_send.py`
- `app/run_daily_pipeline.sh`
- `.env.example`
- `.gitignore`
- `requirements.txt`
- `README.md`
- `data/target_chats.example.txt`
- `deploy/systemd/telegram-summary.service`
- `deploy/systemd/telegram-summary.timer`

Do **not** upload your real `.env`, `messages.db`, session file, or your personal target chat list.
