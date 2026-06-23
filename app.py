import warnings

# Suppress serialization and deprecation warnings cluttering the console
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")
warnings.filterwarnings("ignore", category=DeprecationWarning)

import uuid
import time
import streamlit as st

# Import your compiled LangGraph instance
from src.graph import bot_graph

st.set_page_config(
    page_title="Magic English Companion",
    layout="wide",
    page_icon="🧸"
)

# 1. Master dict for Chat Histories
if "conversations" not in st.session_state:
    st.session_state.conversations = {}

# 2. Master dict for Tutor Metrics
if "thread_metrics" not in st.session_state:
    st.session_state.thread_metrics = {}

def create_new_chat_session():
    new_id = str(uuid.uuid4())
    st.session_state.thread_id = new_id
    st.session_state.conversations[new_id] = []
    st.session_state.thread_metrics[new_id] = {
        "level": "L1", 
        "mode": "Conversation", 
        "mood": "Happy"
    }
    return new_id

# Initialize first session
if "thread_id" not in st.session_state:
    create_new_chat_session()


# ===================== SIDEBAR =====================
with st.sidebar:
    st.title("⚙️ Classroom Control")

    st.markdown(f"**Session ID:** `{st.session_state.thread_id[:8]}`")

    if st.button("🧹 Clear Current Chat"):
        st.session_state.conversations[st.session_state.thread_id] = []
        st.rerun()
        
    st.title("💬 Past Lessons")

    # List all conversations
    for tid, msgs in st.session_state.conversations.items():
        title = "New Chat"
        for m in msgs:
            if m["role"] == "user":
                title = m["content"][:28] + "..."
                break

        if st.button(title, key=tid, use_container_width=True):
            st.session_state.thread_id = tid
            st.rerun()

    st.divider()
    
    if st.button("➕ New Lesson (New Chat)", use_container_width=True):
        create_new_chat_session()
        st.rerun()
        
    st.divider()
    
    active_stats = st.session_state.thread_metrics[st.session_state.thread_id]
    st.subheader("📊 Child Tracker")
    st.metric(label="English Level", value=active_stats["level"])
    st.metric(label="Tutor Mode", value=active_stats["mode"])
    st.metric(label="Detected Mood", value=active_stats["mood"])

    st.subheader("🔍 Debug")
    show_debug = st.toggle("Show LangGraph Output", value=False)


# ===================== MAIN =====================
st.title("🧸 Magic English Companion")
st.caption("AI Tutor for children under 7 | Powered by gpt-4.1-nano-2025-04-14")

current_thread = st.session_state.thread_id

if current_thread not in st.session_state.conversations:
    st.session_state.conversations[current_thread] = []
    st.session_state.thread_metrics[current_thread] = {"level": "L1", "mode": "Conversation", "mood": "Happy"}

st.session_state.messages = st.session_state.conversations[current_thread]
active_stats = st.session_state.thread_metrics[current_thread]


# ===================== CHAT DISPLAY =====================
chat_container = st.container()

with chat_container:
    if not st.session_state.messages:
        st.info("👋 **Welcome!** Try saying *'Hello!'* or *'Look at my dog!'* to start learning.")
        
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            
            # --- PERSISTENT SUB-FIELD DISPLAY ---
            # If it's an assistant message and contains metadata, render it conditionally
            if msg["role"] == "assistant" and "metadata" in msg:
                meta = msg["metadata"]
                if show_debug:
                    st.caption(f"⏱️ [Latency: {meta['latency']:.2f}s] | [Level: {meta['level']}] | [Mode: {meta['mode']}] | [Mood: {meta['mood']}]")
                else:
                    st.caption(f"⚡ Latency: {meta['latency']:.2f}s")


# ===================== INPUT =====================
prompt = st.chat_input("Talk to your English buddy...")

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.markdown(prompt)

    # ===================== LANGGRAPH CALL =====================
    with st.chat_message("assistant"):
        with st.spinner("Thinking... 🤔"):
            start_time = time.time()

            try:
                graph_config = {"configurable": {"thread_id": current_thread}}
                
                payload = {
                    "user_input": prompt,
                    "current_level": active_stats["level"],
                    "current_mode": active_stats["mode"],
                    "child_mood": active_stats["mood"]
                }
                
                output_state = bot_graph.invoke(payload, config=graph_config)
                
                answer = output_state["response"]
                latency = time.time() - start_time
                
                new_lvl = output_state.get("current_level", active_stats["level"])
                new_mode = output_state.get("current_mode", active_stats["mode"])
                new_mood = output_state.get("child_mood", active_stats["mood"])
                
                st.session_state.thread_metrics[current_thread].update({
                    "level": new_lvl,
                    "mode": new_mode,
                    "mood": new_mood
                })

            except Exception as e:
                answer = f"❌ System Error: {str(e)}"
                latency = 0.0
                new_lvl, new_mode, new_mood = active_stats["level"], active_stats["mode"], active_stats["mood"]

            st.markdown(answer)

    # 2. Save assistant message along with its tracking values
    st.session_state.messages.append({
        "role": "assistant",
        "content": answer,
        "metadata": {
            "latency": latency,
            "level": new_lvl,
            "mode": new_mode,
            "mood": new_mood
        }
    })
    
    st.rerun()