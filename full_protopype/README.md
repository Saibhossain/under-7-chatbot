# 🧸 Barnaby's Magic English Companion - Full Latency-Optimized Prototype

This folder contains a fully optimized, production-ready prototype of the English tutoring chatbot for children under 7, along with an integrated Parental Control Panel. 

By restructuring the AI execution model, we have reduced the user-facing response latency from **>2.0 seconds** to **0.3s - 0.6s**.

---

## ⚡ Latency Optimization Strategy (Decoupled Architecture)

In the original implementation, each message sent by the child executed a multi-node LangGraph pipeline sequentially:
1. **Safety Audit Node** (LLM call)
2. **State & Mood Analyzer Node** (LLM call)
3. **Response Generator Node** (LLM call)

This required **3 sequential LLM network round-trips**, leading to high latency (>2s) that disrupts a child's learning momentum.

### The New Architecture:
We decouple the user-facing path from the auditing path:
1. **Child Chatbot Path (Synchronous, Low-Latency)**:
   - When the child sends a message, the chatbot retrieves the active session settings (current level, current mode, and theme topic) directly from a local SQLite database (`db.py`).
   - It performs **exactly one** LLM call to generate the response, passing safety instructions in the system prompt itself.
   - The response is saved and rendered immediately. 
   - **Target Latency:** `0.3s - 0.6s`.
2. **Parent Audit Path (Asynchronous, Background Thread)**:
   - Immediately after the tutor's response is generated and sent to the child, the app starts a **background Python thread**.
   - This thread makes a second LLM call in the background to analyze the child's mood, recommended level, mode, and safety status.
   - The results are saved to the database.
   - If the parent's manual override is disabled, the session's active level/mode are updated in the database, meaning the **next** user turn will naturally adapt to these values without blocking the current turn.

---

## 📁 File Structure

```
full_protopype/
├── README.md               # This documentation file
├── db.py                   # SQLite database helper for chat logs, settings, and audits
├── llm_utils.py            # Chat generator (fast single-LLM) & background evaluation logic
└── app.py                  # Dual-view Streamlit dashboard (Kids Playroom & Parental Control Panel)
```

---

## 💾 Database Schema (`db.py`)

A local SQLite database (`under7_companion.db`) is automatically initialized to handle log monitoring and session persistence:

### 1. `sessions` Table
Tracks active curriculum parameters and parent settings:
* `session_id` (TEXT, Primary Key): Unique UUID.
* `current_level` (TEXT): Active learning level (`L1`, `L2`, `L3`).
* `current_mode` (TEXT): Active mode (`Learning`, `Conversation`, `Engagement`, `Support`).
* `active_topic` (TEXT): Custom topic selected by parent (e.g., "Colors", "Animals", "Space").
* `mood` (TEXT): Last detected child mood.
* `override_active` (INTEGER): `1` if parent manual override is active, `0` if AI autopilot is active.
* `created_at` (TEXT): Timestamp.

### 2. `chat_logs` Table
Logs all chat metrics and background evaluations:
* `id` (INTEGER, PK Autoincrement)
* `session_id` (TEXT): FK reference.
* `role` (TEXT): `'user'` or `'assistant'`.
* `content` (TEXT): Text content of message.
* `timestamp` (TEXT): Date/time.
* `latency` (REAL): Response generation latency (seconds).
* `level_at_turn` / `mode_at_turn` / `topic_at_turn` (TEXT): The settings configured when the turn occurred.
* `bg_evaluated` (INTEGER): `0` (pending) or `1` (evaluated).
* `evaluated_level` / `evaluated_mode` / `evaluated_mood` (TEXT): Background analysis results.
* `is_safe` (INTEGER): `1` (safe) or `0` (flagged unsafe).

---

## 🚀 How to Run the App

1. Ensure your environment variables are configured in the root `.env` file (especially `OPENAI_API_KEY` and `MODEL`).
2. Navigate to the `full_protopype` folder and start the Streamlit app:
   ```bash
   cd full_protopype
   streamlit run app.py
   ```
3. Use the sidebar to switch views:
   - **🧸 Kids Playroom**: Simple, modern, child-friendly design. It hides technical metrics and offers quick clickable response buttons.
   - **🔐 Parental Control Panel**: View real-time logs, customize learning topics, toggle AI autopilot/manual override, and review latency benchmarks.
