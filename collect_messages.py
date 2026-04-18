import os
import re
import sqlite3
from datetime import datetime, timedelta
from dotenv import load_dotenv
from pyrogram import Client

load_dotenv()

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
SESSION_NAME = os.getenv("SESSION_NAME", "telegram_summary")

DB_PATH = "data/messages.db"
TARGET_FILE = "data/target_chats.txt"

if not API_ID or not API_HASH:
    raise RuntimeError("Missing API_ID or API_HASH in .env")


def load_target_chat_ids(path: str) -> list[int]:
    result: list[int] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            result.append(int(line))
    return result


def iso_dt(dt: datetime) -> str:
    return dt.isoformat(sep=" ", timespec="seconds")


def get_active_window(now: datetime | None = None) -> tuple[datetime, datetime]:
    if now is None:
        now = datetime.now().astimezone()

    today_2200 = now.replace(hour=22, minute=0, second=0, microsecond=0)

    if now >= today_2200:
        window_end = today_2200
    else:
        window_end = today_2200 - timedelta(days=1)

    window_start = window_end - timedelta(days=1)
    return window_start, window_end


def clean_text(text: str) -> str:
    if not text:
        return ""

    text = text.replace("\r\n", "\n").replace("\r", "\n")

    lines = text.split("\n")
    cleaned_lines = []

    skip_patterns = [
        r"^\s*\d+\s+תגובות\s*$",
        r"^\s*תגובה\s+אחת\s*$",
        r"^\s*תגובות\s*$",
        r"^\s*\d+\s+comments?\s*$",
        r"^\s*reply here\s*$",
        r"^\s*click here to comment\s*$",
        r"^\s*כדי להגיב לכתבה לחצו כאן\s*$",
        r"^\s*לערוץ הדיונים\s*-\s*לחצו כאן\s*$",
        r"^\s*https?://t\.me/.*$",
    ]

    compiled = [re.compile(p, flags=re.IGNORECASE) for p in skip_patterns]

    for line in lines:
        stripped = line.strip()
        if any(p.match(stripped) for p in compiled):
            continue
        cleaned_lines.append(line)

    text = "\n".join(cleaned_lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_text(message) -> str:
    raw = message.text or message.caption or ""
    return clean_text(raw)


def insert_message(conn, chat_id: int, chat_name: str, message_id: int, message_date: str, window_end: str, text: str) -> int:
    sql = """
    INSERT OR IGNORE INTO raw_messages (
        chat_id,
        chat_name,
        message_id,
        message_date,
        window_end,
        text,
        is_ad_candidate,
        processed
    )
    VALUES (?, ?, ?, ?, ?, ?, 0, 0)
    """
    cur = conn.execute(
        sql,
        (chat_id, chat_name, message_id, message_date, window_end, text),
    )
    return cur.rowcount


def ensure_job(conn, chat_id: int, chat_name: str, window_end: str) -> None:
    now = datetime.now().isoformat(sep=" ", timespec="seconds")
    sql = """
    INSERT INTO jobs (chat_id, chat_name, window_end, status, last_error, created_at, updated_at)
    VALUES (?, ?, ?, 'pending', NULL, ?, ?)
    ON CONFLICT(chat_id, window_end) DO UPDATE SET
        updated_at = excluded.updated_at
    """
    conn.execute(sql, (chat_id, chat_name, window_end, now, now))


def main():
    target_chat_ids = load_target_chat_ids(TARGET_FILE)
    window_start, window_end = get_active_window()

    print(f"Active summary window start: {iso_dt(window_start)}")
    print(f"Active summary window end:   {iso_dt(window_end)}")

    app = Client(
        name=SESSION_NAME,
        api_id=API_ID,
        api_hash=API_HASH,
        workdir="data",
    )

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    total_inserted = 0
    total_seen_in_window = 0

    try:
        with app:
            for chat_id in target_chat_ids:
                chat = app.get_chat(chat_id)
                chat_name = chat.title or chat.first_name or str(chat_id)

                print(f"\nCollecting from: {chat_name} ({chat_id})")

                inserted_for_chat = 0
                seen_for_chat = 0

                for msg in app.get_chat_history(chat_id):
                    msg_dt = msg.date

                    if msg_dt.tzinfo is None:
                        msg_dt = msg_dt.replace(tzinfo=window_end.tzinfo)

                    if msg_dt <= window_start:
                        break

                    if not (window_start < msg_dt <= window_end):
                        continue

                    cleaned = extract_text(msg)
                    if not cleaned:
                        continue

                    seen_for_chat += 1
                    total_seen_in_window += 1

                    inserted = insert_message(
                        conn=conn,
                        chat_id=chat_id,
                        chat_name=chat_name,
                        message_id=msg.id,
                        message_date=iso_dt(msg_dt),
                        window_end=iso_dt(window_end),
                        text=cleaned,
                    )

                    ensure_job(
                        conn=conn,
                        chat_id=chat_id,
                        chat_name=chat_name,
                        window_end=iso_dt(window_end),
                    )

                    inserted_for_chat += inserted
                    total_inserted += inserted

                conn.commit()
                print(f"Seen messages in active window: {seen_for_chat}")
                print(f"Inserted new rows: {inserted_for_chat}")

        print("\nDone.")
        print(f"Total seen in active window: {total_seen_in_window}")
        print(f"Total newly inserted rows: {total_inserted}")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
