import logging
from uuid import UUID
from typing import List, Dict, Any, Optional
from src.storage.db import get_db

logger = logging.getLogger(__name__)

def create_session(tenant_id: UUID) -> str:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO chat_sessions (tenant_id) VALUES (%s) RETURNING id",
                (tenant_id,)
            )
            session_id = cur.fetchone()[0]
            conn.commit()
            return str(session_id)

def get_session(session_id: UUID) -> Optional[Dict[str, Any]]:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, tenant_id FROM chat_sessions WHERE id = %s", (session_id,))
            row = cur.fetchone()
            if row:
                return {"id": str(row[0]), "tenant_id": str(row[1])}
            return None

def add_message(session_id: UUID, role: str, content: str):
    if role not in ('user', 'ai'):
        raise ValueError("Role must be 'user' or 'ai'")

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO chat_messages (session_id, role, content)
                VALUES (%s, %s, %s)
                """,
                (session_id, role, content)
            )
            conn.commit()

def get_chat_history(session_id: UUID, limit: int = 10) -> List[Dict[str, str]]:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT role, content
                FROM chat_messages
                WHERE session_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (session_id, limit)
            )
            rows = cur.fetchall()

            history = [{"role": row[0], "content": row[1]} for row in rows]
            return history[::-1]

def get_full_chat_history(session_id: UUID) -> List[Dict[str, str]]:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT role, content
                FROM chat_messages
                WHERE session_id = %s
                ORDER BY created_at ASC
                """,
                (session_id,)
            )
            rows = cur.fetchall()
            return [{"role": row[0], "content": row[1]} for row in rows]

def delete_session(session_id: UUID):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM chat_messages WHERE session_id = %s", (session_id,))
            cur.execute("DELETE FROM chat_sessions WHERE id = %s", (session_id,))
            conn.commit()
            logger.info(f"Deleted session {session_id} and its history.")
