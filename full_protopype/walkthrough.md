# Walkthrough - Split Apps, Naming, Notebook, and DB Explorer

We have split the frontend into separate applications, resolved Pydantic serialization warnings, implemented human-readable conversation session thread names, generated a LangGraph latency-optimized Jupyter notebook, and created a database explorer tool.

## Changes Made

### 1. Separate Streamlit Applications
We split the unified dashboard into three distinct applications inside `full_protopype/`:
- **[app_kids.py](file:///Users/mdsaibhossain/code/python/under-7-chatbot/full_protopype/app_kids.py) (Kids Playroom)**: Kid-centric playroom view with custom pastel colors, quick suggests, and an active conversation thread selector displaying human-readable thread names.
- **[app_parent.py](file:///Users/mdsaibhossain/code/python/under-7-chatbot/full_protopype/app_parent.py) (Parental Control Panel)**: Parental control metrics telemetry, overrides, active topic setting, and diagnostic log audit view.
- **[app_db_explorer.py](file:///Users/mdsaibhossain/code/python/under-7-chatbot/full_protopype/app_db_explorer.py) (Database Schema & Editor)**: System utility enabling dashboard inspections of tables, columns, rows, and providing deletion controls.

### 2. Human-Readable Session Threads
- Modified [db.py](file:///Users/mdsaibhossain/code/python/under-7-chatbot/full_protopype/db.py) to add a `thread_name` column to the `sessions` table.
- Configured thread creation to set the name to `"Session [4-char-UUID] - [Active Topic]"` (e.g., `Session 4e3a - Ballons`).
- Updated the name automatically whenever the active topic changes.

### 3. Suppressed Pydantic Warnings
- Modified [agents.py](file:///Users/mdsaibhossain/code/python/under-7-chatbot/full_protopype/agents.py) to import `warnings` and silence user warnings coming from `pydantic`. This clears the console logs of serializer warning tracebacks.

### 4. LangGraph Jupyter Notebook
- Generated a self-contained notebook **[latency_optimized.ipynb](file:///Users/mdsaibhossain/code/python/under-7-chatbot/full_protopype/latency_optimized.ipynb)** containing:
  - An introduction to the child-tutor latency optimization architecture.
  - Complete FAISS Local RAG database setup parsing `books.txt`.
  - A compiled **LangGraph `StateGraph`** implementing the multi-agent system.
  - A CLI loop-based UI with interactive input allowing conversations with telemetry feedback.

---

## Latency Test Results

The updated results using the environment-loaded search API key are documented in [latency_test_result.md](file:///Users/mdsaibhossain/code/python/under-7-chatbot/full_protopype/latency_test_result.md):

| Query | LLM Response | Latency (s) | Tools Used | Agent Name |
| :--- | :--- | :--- | :--- | :--- |
| **Hello Barnaby! 🧸** | Hi hi! 😊 You're so sweet! Want to sing a song or play... | **1.026s** | None | LearningChatbotAgent |
| **Who is Sam and what color is his balloon?** | Sam is a little boy, and his balloon is big and red! 🎈 ... | **1.513s** | RAG | LearningChatbotAgent |
| **Tell me a fact about puppies** | Puppies are born blind and deaf, but they love to feel... | **1.956s** | WebSearch | LearningChatbotAgent |

### Target Validation:
- **Chatbot WebSearch tool execution**: Correctly ran search using the `TAVILY_API` key from `.env` — **PASSED** ✅
- **RAG & Conversational Latency**: Remained stable and validated — **PASSED** ✅
