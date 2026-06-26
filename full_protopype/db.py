import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "under7_companion.db")

def get_connection():
    """Create a new database connection with dictionary-like row access."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database tables if they do not exist."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Create sessions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            current_level TEXT NOT NULL DEFAULT 'L1',
            current_mode TEXT NOT NULL DEFAULT 'Conversation',
            active_topic TEXT NOT NULL DEFAULT 'General English',
            mood TEXT NOT NULL DEFAULT 'Happy',
            override_active INTEGER NOT NULL DEFAULT 0, -- 1 if manually overridden by parent
            created_at TEXT NOT NULL
        )
    """)
    
    # Create chat_logs table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL, -- 'user' or 'assistant'
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            latency REAL, -- Null for user inputs, populated for assistant response
            level_at_turn TEXT, -- Level configuration when the message was sent
            mode_at_turn TEXT, -- Mode configuration when the message was sent
            topic_at_turn TEXT, -- Topic configuration when the message was sent
            bg_evaluated INTEGER NOT NULL DEFAULT 0, -- 0 = pending, 1 = analyzed
            evaluated_level TEXT, -- Level computed by background LLM
            evaluated_mode TEXT, -- Mode computed by background LLM
            evaluated_mood TEXT, -- Mood computed by background LLM
            is_safe INTEGER, -- 1 = safe, 0 = unsafe (null if pending)
            FOREIGN KEY (session_id) REFERENCES sessions (session_id)
        )
    """)
    
    conn.commit()
    conn.close()

def create_session(session_id, current_level='L1', current_mode='Conversation', active_topic='General English'):
    """Create a new chat session in the database if it doesn't already exist."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT OR IGNORE INTO sessions (session_id, current_level, current_mode, active_topic, mood, override_active, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (session_id, current_level, current_mode, active_topic, 'Happy', 0, datetime.now().isoformat())
        )
        conn.commit()
    finally:
        conn.close()

def get_session(session_id):
    """Retrieve session details."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def get_all_sessions():
    """Retrieve list of all sessions in descending order of creation."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM sessions ORDER BY created_at DESC")
        rows = cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def update_session_bg_eval(session_id, level=None, mode=None, mood=None):
    """Updates active session settings computed in background. Will NOT override if parent override is active."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Check if parent override is active
        cursor.execute("SELECT override_active FROM sessions WHERE session_id = ?", (session_id,))
        row = cursor.fetchone()
        if row and row['override_active'] == 1:
            # Skip updating level/mode but update mood
            if mood:
                cursor.execute("UPDATE sessions SET mood = ? WHERE session_id = ?", (mood, session_id))
        else:
            # Update all
            updates = []
            params = []
            if level:
                updates.append("current_level = ?")
                params.append(level)
            if mode:
                updates.append("current_mode = ?")
                params.append(mode)
            if mood:
                updates.append("mood = ?")
                params.append(mood)
            
            if updates:
                params.append(session_id)
                cursor.execute(f"UPDATE sessions SET {', '.join(updates)} WHERE session_id = ?", tuple(params))
        conn.commit()
    finally:
        conn.close()

def update_session_parent_settings(session_id, level=None, mode=None, active_topic=None, override_active=None):
    """Updates session settings explicitly from the Parental Dashboard."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        updates = []
        params = []
        if level is not None:
            updates.append("current_level = ?")
            params.append(level)
        if mode is not None:
            updates.append("current_mode = ?")
            params.append(mode)
        if active_topic is not None:
            updates.append("active_topic = ?")
            params.append(active_topic)
        if override_active is not None:
            updates.append("override_active = ?")
            params.append(override_active)
            
        if updates:
            params.append(session_id)
            cursor.execute(f"UPDATE sessions SET {', '.join(updates)} WHERE session_id = ?", tuple(params))
            conn.commit()
    finally:
        conn.close()

def log_chat_message(session_id, role, content, latency=None, level_at_turn=None, mode_at_turn=None, topic_at_turn=None):
    """Log a child/tutor message in the database. Returns the row ID of the inserted message."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """INSERT INTO chat_logs 
               (session_id, role, content, timestamp, latency, level_at_turn, mode_at_turn, topic_at_turn, bg_evaluated) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)""",
            (session_id, role, content, datetime.now().isoformat(), latency, level_at_turn, mode_at_turn, topic_at_turn)
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()

def update_chat_message_bg_eval(chat_log_id, evaluated_level, evaluated_mode, evaluated_mood, is_safe):
    """Saves the output of the background LLM evaluations for a specific chat message."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """UPDATE chat_logs 
               SET evaluated_level = ?, evaluated_mode = ?, evaluated_mood = ?, is_safe = ?, bg_evaluated = 1 
               WHERE id = ?""",
            (evaluated_level, evaluated_mode, evaluated_mood, 1 if is_safe else 0, chat_log_id)
        )
        conn.commit()
    finally:
        conn.close()

def get_chat_history(session_id, limit=10):
    """Retrieve chat history for a session."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT * FROM chat_logs WHERE session_id = ? ORDER BY id ASC",
            (session_id,)
        )
        rows = cursor.fetchall()
        # Filter and return as list of dicts
        history = [dict(r) for r in rows]
        return history[-limit:] if limit else history
    finally:
        conn.close()

def get_session_stats(session_id):
    """Calculates statistics for a session (e.g. average chatbot response latency, evaluation counts, etc.)."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Chatbot latency stats
        cursor.execute(
            "SELECT AVG(latency), MAX(latency), MIN(latency), COUNT(*) FROM chat_logs WHERE session_id = ? AND role = 'assistant'",
            (session_id,)
        )
        avg_lat, max_lat, min_lat, count = cursor.fetchone()
        
        # Unsafe flags count
        cursor.execute(
            "SELECT COUNT(*) FROM chat_logs WHERE session_id = ? AND is_safe = 0",
            (session_id,)
        )
        unsafe_count = cursor.fetchone()[0]
        
        return {
            "avg_latency": avg_lat if avg_lat is not None else 0.0,
            "max_latency": max_lat if max_lat is not None else 0.0,
            "min_latency": min_lat if min_lat is not None else 0.0,
            "total_tutor_turns": count,
            "unsafe_turns": unsafe_count
        }
    finally:
        conn.close()

# Initialize DB on load
init_db()
