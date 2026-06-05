import json
import os
import sqlite3
from pathlib import Path
from typing import Dict, List

DB_PATH = Path(os.getenv("MEMORY_DB_PATH", "bot_memory.db"))


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True) if DB_PATH.parent != Path(".") else None
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_memory (
                chat_id TEXT PRIMARY KEY,
                messages TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()


def get_history(chat_id: int | str) -> List[Dict[str, str]]:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT messages FROM chat_memory WHERE chat_id = ?",
            (str(chat_id),),
        ).fetchone()

    if not row:
        return []

    try:
        messages = json.loads(row[0])
        if isinstance(messages, list):
            return messages
    except json.JSONDecodeError:
        pass

    return []


def save_history(chat_id: int | str, messages: List[Dict[str, str]]) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO chat_memory (chat_id, messages, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(chat_id) DO UPDATE SET
                messages = excluded.messages,
                updated_at = CURRENT_TIMESTAMP
            """,
            (str(chat_id), json.dumps(messages, ensure_ascii=False)),
        )
        conn.commit()


def clear_history(chat_id: int | str) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM chat_memory WHERE chat_id = ?", (str(chat_id),))
        conn.commit()
