import os
import sqlite3
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()

DB_PATH = "data/messages.db"
PRIORITY_CHAT_ID = os.getenv("PRIORITY_CHAT_ID", "").strip()
PRIORITY_CHAT_ID = int(PRIORITY_CHAT_ID) if PRIORITY_CHAT_ID else None


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        row = conn.execute(
            """
            SELECT window_end
            FROM jobs
            WHERE status = 'pending'
            ORDER BY window_end DESC
            LIMIT 1
            """
        ).fetchone()

        if not row:
            print("No pending jobs found.")
            return

        window_end = row["window_end"]

        rows = conn.execute(
            """
            SELECT chat_id, chat_name, message_date, text
            FROM raw_messages
            WHERE window_end = ?
            ORDER BY message_date ASC, chat_name ASC
            """,
            (window_end,),
        ).fetchall()

        if not rows:
            print("No raw messages found for pending window.")
            return

        grouped = defaultdict(list)
        total_messages = 0

        for r in rows:
            grouped[(r["chat_id"], r["chat_name"])].append(
                {
                    "message_date": r["message_date"],
                    "text": r["text"],
                }
            )
            total_messages += 1

        print(f"Window end: {window_end}")
        print(f"Total messages in combined batch: {total_messages}")
        print(f"Total source groups: {len(grouped)}")
        print("=" * 80)

        batch_lines = [f"Summary window end: {window_end}", ""]

        sorted_items = sorted(
            grouped.items(),
            key=lambda x: (0 if PRIORITY_CHAT_ID and x[0][0] == PRIORITY_CHAT_ID else 1, x[0][1].lower()),
        )

        for (chat_id, chat_name), messages in sorted_items:
            priority_label = "high" if PRIORITY_CHAT_ID and chat_id == PRIORITY_CHAT_ID else "normal"

            batch_lines.append(f"### Source: {chat_name}")
            batch_lines.append(f"Source priority: {priority_label}")
            batch_lines.append(f"Messages count: {len(messages)}")
            batch_lines.append("")

            for msg in messages:
                batch_lines.append(f"[{msg['message_date']}]")
                batch_lines.append(msg["text"])
                batch_lines.append("")

            batch_lines.append("-" * 60)
            batch_lines.append("")

        final_text = "\n".join(batch_lines).strip()

        output_path = "data/combined_batch.txt"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(final_text)

        print(f"Combined batch written to: {output_path}")
        print("=" * 80)
        print(final_text[:5000])

        if len(final_text) > 5000:
            print("\n... output truncated in terminal ...")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
