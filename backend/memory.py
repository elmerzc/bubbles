"""
Bubbles Memory System
- Context: Recent conversation history (last N exchanges)
- Persistent: Facts about the child across sessions
- Personality: Tracks child's communication style
"""
import json
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "bubbles_memory.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Create tables if they don't exist."""
    conn = get_db()
    c = conn.cursor()
    # Conversation history
    c.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            role TEXT,  -- 'child' or 'bubbles'
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Persistent facts (name, preferences, etc.)
    c.execute("""
        CREATE TABLE IF NOT EXISTS facts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            key TEXT UNIQUE,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Personality traits
    c.execute("""
        CREATE TABLE IF NOT EXISTS personality (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            trait TEXT,
            value REAL DEFAULT 0.5,  -- 0.0 to 1.0 scale
            count INTEGER DEFAULT 1,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(session_id, trait)
        )
    """)
    conn.commit()
    conn.close()

def add_message(session_id: str, role: str, content: str):
    """Add a message to conversation history."""
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
        (session_id, role, content)
    )
    conn.commit()
    conn.close()

def get_recent_context(session_id: str, limit: int = 5) -> list:
    """Get last N conversation exchanges."""
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT role, content FROM messages 
        WHERE session_id = ? 
        ORDER BY created_at DESC LIMIT ?
    """, (session_id, limit * 2))  # *2 because each exchange has 2 messages
    rows = c.fetchall()
    conn.close()
    # Reverse to get chronological order
    return [(dict(row)['role'], dict(row)['content']) for row in reversed(rows)]

def set_fact(session_id: str, key: str, value: str):
    """Set a persistent fact."""
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        INSERT INTO facts (session_id, key, value) VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
    """, (session_id, key, value))
    conn.commit()
    conn.close()

def get_facts(session_id: str) -> dict:
    """Get all facts for a session."""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT key, value FROM facts WHERE session_id = ?", (session_id,))
    rows = c.fetchall()
    conn.close()
    return {dict(row)['key']: dict(row)['value'] for row in rows}

def update_personality(session_id: str, trait: str, adjustment: float):
    """Update a personality trait (0.0 to 1.0)."""
    conn = get_db()
    c = conn.cursor()
    try:
        c.execute("""
            INSERT INTO personality (session_id, trait, value, count)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(session_id, trait) DO UPDATE SET 
                value = CASE 
                    WHEN personality.count + 1 > 1 THEN (personality.value * personality.count + ?) / (personality.count + 1)
                    ELSE ?
                END,
                count = personality.count + 1,
                updated_at = CURRENT_TIMESTAMP
        """, (session_id, trait, adjustment, adjustment, adjustment))
    except sqlite3.OperationalError:
        # Table doesn't have unique constraint yet, do a simple update or insert
        c.execute("SELECT count FROM personality WHERE session_id = ? AND trait = ?", (session_id, trait))
        row = c.fetchone()
        if row:
            c.execute("""
                UPDATE personality SET 
                    value = (value * count + ?) / (count + 1),
                    count = count + 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE session_id = ? AND trait = ?
            """, (adjustment, session_id, trait))
        else:
            c.execute("""
                INSERT INTO personality (session_id, trait, value, count)
                VALUES (?, ?, ?, 1)
            """, (session_id, trait, adjustment))
    conn.commit()
    conn.close()

def get_personality(session_id: str) -> dict:
    """Get personality traits for a session."""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT trait, value FROM personality WHERE session_id = ?", (session_id,))
    rows = c.fetchall()
    conn.close()
    return {dict(row)['trait']: dict(row)['value'] for row in rows}

def build_context_prompt(session_id: str) -> str:
    """Build conversation context from recent messages."""
    recent = get_recent_context(session_id, limit=3)
    if not recent:
        return ""
    context = "\nPrevious conversation:\n"
    for role, content in recent:
        speaker = "Child" if role == "child" else "Bubbles"
        context += f"- {speaker}: {content}\n"
    return context.strip()

def build_facts_prompt(session_id: str) -> str:
    """Build persistent facts prompt."""
    facts = get_facts(session_id)
    if not facts:
        return ""
    prompt = "\nWhat you know about this child:"
    for key, value in facts.items():
        prompt += f"\n- {key}: {value}"
    return prompt

def build_personality_prompt(session_id: str) -> str:
    """Build personality-aware prompt."""
    traits = get_personality(session_id)
    if not traits:
        return ""
    # Map traits to communication style
    if traits.get('silly', 0.5) > 0.7:
        style = "extra silly"
    elif traits.get('quiet', 0.5) < 0.3:
        style = "gentle and calm"
    else:
        style = "balanced"
    return f"\nThis child responds best to {style} communication."

# Initialize on import
init_db()
