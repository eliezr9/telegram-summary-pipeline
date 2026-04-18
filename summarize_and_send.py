import os
import sqlite3
import subprocess
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv
from pyrogram import Client
from google import genai

load_dotenv()

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
SESSION_NAME = os.getenv("SESSION_NAME", "telegram_summary")
SUMMARY_CHANNEL_ID = int(os.getenv("SUMMARY_CHANNEL_ID", "0"))
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
SUMMARY_TITLE = os.getenv("SUMMARY_TITLE", "Daily Summary")
SUMMARY_TOPIC = os.getenv("SUMMARY_TOPIC", "updates from selected Telegram sources")
IMPORTANT_ENTITIES = os.getenv("IMPORTANT_ENTITIES", "").strip()

DB_PATH = "data/messages.db"
COMBINED_BATCH_PATH = "data/combined_batch.txt"

MAX_TELEGRAM_MESSAGE_LEN = 3500
MAX_TELEGRAM_PARTS = 3
GEMINI_MAX_RETRIES = 3
GEMINI_RETRY_DELAY_SECONDS = 60


def get_latest_pending_window(conn):
    row = conn.execute(
        """
        SELECT window_end
        FROM jobs
        WHERE status = 'pending'
        ORDER BY window_end DESC
        LIMIT 1
        """
    ).fetchone()
    return row["window_end"] if row else None


def format_window_range(window_end_str: str) -> str:
    window_end = datetime.fromisoformat(window_end_str)
    window_start = window_end - timedelta(days=1)
    return f"{window_start:%d.%m %H:%M} → {window_end:%d.%m %H:%M}"


def build_prompt(batch_text: str, window_end: str) -> str:
    window_range = format_window_range(window_end)

    important_entities_block = ""
    if IMPORTANT_ENTITIES:
        important_entities_block = (
            "\n🧠 Important entities:\n"
            f"- If statements or posts from these people/entities are materially relevant, include them: {IMPORTANT_ENTITIES}\n"
            "- If there is a highly relevant direct quote, include one short and accurate quote inside the relevant bullet.\n"
            "- Do not let any single person dominate the whole summary unless they truly dominated the day.\n"
        )

    return f"""
You are creating a professional daily summary in Hebrew from selected Telegram sources.

🎯 Goal:
Produce a short, sharp, readable end-of-day summary that a person can scan in under a minute.

⚠️ Rules:
- Write in Hebrew only.
- Ignore ads, channel slogans, religious texts, links, greetings, and repetitive noise.
- Merge duplicates across sources.
- Keep only the most important developments.
- If something is uncertain, say so carefully.
- Do not present commentary as fact.
- If there are violent details, keep them factual and restrained.
{important_entities_block}
📌 Required structure:
🗓️ {SUMMARY_TITLE}
🕒 חלון זמן: {window_range}

🧭 תמונת מצב:
A short opening paragraph of 3–5 lines.

📌 עיקרי ההתפתחויות:
1. 🔹 [Short title]
   [One or two short lines]

2. 🔹 [Short title]
   [One or two short lines]

3. 🔹 [Short title]
   [One or two short lines]

4. 🔹 [Short title]
   [One or two short lines]

If necessary, use 5 or 6 bullets, but prefer 4.
Do not exceed 6 bullets.

⚠️ הערכות:
2–3 lines only, and only if they add real value.

🔎 מבט מסכם:
2–3 lines reflecting the overall picture.

🚫 Hard constraints:
- Keep it significantly shorter than the source material.
- No repetition.
- No leftover source signatures or slogans.
- Better to omit a minor detail than overload the summary.

Topic of the digest:
{SUMMARY_TOPIC}

Source material:
{batch_text}
""".strip()


def build_compression_prompt(summary_text: str, window_end: str) -> str:
    window_range = format_window_range(window_end)

    return f"""
Compress the following Hebrew summary aggressively while keeping only the most important information.

🗓️ {SUMMARY_TITLE}
🕒 חלון זמן: {window_range}

🧭 תמונת מצב:
2–3 short lines.

📌 עיקרי ההתפתחויות:
3–5 bullets only.
Each bullet should have:
🔹 short title
one short explanation line

⚠️ הערכות:
1–2 short lines

🔎 מבט מסכם:
2 short lines

Rules:
- Remove secondary details.
- Remove repetition.
- Keep only the highest-value items.
- Keep the result easy to read in Telegram.

Summary to compress:
{summary_text}
""".strip()


def generate_text_once(prompt: str) -> str:
    client = genai.Client(api_key=GEMINI_API_KEY)

    models_to_try = [
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
    ]

    last_error = None

    for model in models_to_try:
        try:
            print(f"Trying model: {model}")
            response = client.models.generate_content(
                model=model,
                contents=prompt,
            )
            text = getattr(response, "text", None)
            if text and text.strip():
                return text.strip()
            last_error = RuntimeError(f"{model} returned empty response")
        except Exception as e:
            print(f"{model} failed: {e}")
            last_error = e

    raise RuntimeError(f"All models failed in this attempt: {last_error}")


def generate_text_with_retry(prompt: str) -> str:
    last_error = None

    for attempt in range(1, GEMINI_MAX_RETRIES + 1):
        try:
            print(f"Gemini overall attempt {attempt}/{GEMINI_MAX_RETRIES}")
            text = generate_text_once(prompt)
            if not text or not text.strip():
                raise RuntimeError("Gemini returned empty response")
            return text.strip()
        except Exception as e:
            last_error = e
            print(f"Gemini attempt {attempt} failed: {e}")
            if attempt < GEMINI_MAX_RETRIES:
                print(f"Waiting {GEMINI_RETRY_DELAY_SECONDS} seconds before retry...")
                time.sleep(GEMINI_RETRY_DELAY_SECONDS)

    raise RuntimeError(f"Gemini failed after {GEMINI_MAX_RETRIES} attempts: {last_error}")


def generate_summary(batch_text: str, window_end: str) -> str:
    return generate_text_with_retry(build_prompt(batch_text, window_end))


def compress_summary(summary_text: str, window_end: str) -> str:
    return generate_text_with_retry(build_compression_prompt(summary_text, window_end))


def pre_trim_batch(text: str, max_chars: int = 12000) -> str:
    if len(text) <= max_chars:
        return text

    print("Pre-trimming batch before sending to AI...")
    return text[-max_chars:]


def split_text_for_telegram(text: str, max_len: int = MAX_TELEGRAM_MESSAGE_LEN) -> list[str]:
    text = text.strip()
    if len(text) <= max_len:
        return [text]

    parts = []
    remaining = text

    while len(remaining) > max_len:
        chunk = remaining[:max_len]

        split_at = chunk.rfind("\n\n")
        if split_at < max_len * 0.5:
            split_at = chunk.rfind("\n")
        if split_at < max_len * 0.5:
            split_at = chunk.rfind(". ")
        if split_at < max_len * 0.5:
            split_at = chunk.rfind(" ")

        if split_at <= 0:
            split_at = max_len

        part = remaining[:split_at].strip()
        if part:
            parts.append(part)

        remaining = remaining[split_at:].strip()

    if remaining:
        parts.append(remaining)

    return parts


def fit_summary_to_telegram(summary: str, window_end: str) -> str:
    attempt = 0
    current = summary

    while True:
        parts = split_text_for_telegram(current)

        if len(parts) <= MAX_TELEGRAM_PARTS and len(current) < 6000:
            return current

        attempt += 1
        print(f"Compressing summary (attempt {attempt})...")
        current = compress_summary(current, window_end)

        if attempt >= 3:
            print("Max compression reached")
            return current


def send_summary_chunks(app: Client, chat_id: int, summary: str):
    parts = split_text_for_telegram(summary)

    if len(parts) == 1:
        app.send_message(chat_id=chat_id, text=parts[0])
        return

    for index, part in enumerate(parts, start=1):
        header = f"({index}/{len(parts)})\n" if index > 1 else ""
        app.send_message(chat_id=chat_id, text=header + part)


def send_failure_message(app: Client, chat_id: int, window_end: str, error_text: str):
    window_range = format_window_range(window_end)
    message = (
        "⚠️ Daily summary failed\n"
        f"🕒 Window: {window_range}\n\n"
        "The summary failed 3 times.\n"
        "The local data was preserved so the run can be retried later.\n\n"
        f"Last error:\n{error_text[:1500]}"
    )
    app.send_message(chat_id=chat_id, text=message)


def delete_window_data(conn, window_end: str):
    conn.execute("DELETE FROM raw_messages WHERE window_end = ?", (window_end,))
    conn.execute("DELETE FROM jobs WHERE window_end = ?", (window_end,))
    conn.commit()


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    app = Client(
        name=SESSION_NAME,
        api_id=API_ID,
        api_hash=API_HASH,
        workdir="data",
    )

    try:
        window_end = get_latest_pending_window(conn)
        if not window_end:
            print("No pending jobs")
            return

        subprocess.run(["python", "app/build_combined_batch.py"], check=True)

        with open(COMBINED_BATCH_PATH, "r", encoding="utf-8") as f:
            batch_text = f.read().strip()

        if not batch_text:
            raise RuntimeError("Combined batch is empty")

        print(f"Generating summary for window: {window_end}")
        batch_text = pre_trim_batch(batch_text)

        try:
            summary = generate_summary(batch_text, window_end)
            summary = fit_summary_to_telegram(summary, window_end)

            print("Sending to Telegram...")
            with app:
                send_summary_chunks(app, SUMMARY_CHANNEL_ID, summary)

            print("Sent successfully")
            delete_window_data(conn, window_end)
            print("Cleaned DB")

        except Exception as e:
            print(f"Summary generation/sending failed: {e}")
            with app:
                send_failure_message(app, SUMMARY_CHANNEL_ID, window_end, str(e))
            raise

    finally:
        conn.close()


if __name__ == "__main__":
    main()
