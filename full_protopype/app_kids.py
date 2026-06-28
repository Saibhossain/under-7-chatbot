import streamlit as st
import uuid
import time
import pandas as pd
from datetime import datetime

# Import database and agents
from db import (
    create_session,
    get_session,
    get_all_sessions,
    get_chat_history,
    log_chat_message,
)
from agents import (
    LearningChatbotAgent,
    ParentalControlAgent,
)

st.set_page_config(
    page_title="Barnaby's Magic English Adventure! 🧸",
    layout="wide",
    page_icon="🧸"
)

# Initialize Session State
if "session_id" not in st.session_state:
    # Set to latest session if available, otherwise start new
    sessions = get_all_sessions()
    if sessions:
        st.session_state.session_id = sessions[0]["session_id"]
    else:
        st.session_state.session_id = str(uuid.uuid4())
        create_session(st.session_state.session_id)

if "chatbot_agent" not in st.session_state:
    st.session_state.chatbot_agent = LearningChatbotAgent()
if "parent_agent" not in st.session_state:
    st.session_state.parent_agent = ParentalControlAgent(st.session_state.chatbot_agent)

# ===================== SIDEBAR NAVIGATION & THREADS =====================
with st.sidebar:
    st.markdown(
        """
        <div style="text-align: center; margin-bottom: 20px;">
            <span style="font-size: 60px;">🎒</span>
            <h2 style="margin: 5px 0 0 0; color: #FF7043; font-family: 'Fredoka', sans-serif;">Playroom Hub</h2>
        </div>
        """, 
        unsafe_allow_html=True
    )
    
    st.divider()
    
    st.markdown("### 💬 Your Conversations")
    
    # Retrieve all sessions
    sessions = get_all_sessions()
    if sessions:
        session_ids = [s["session_id"] for s in sessions]
        # Display human-readable thread name
        session_labels = [s.get("thread_name") or f"Session {s['session_id'][:4]}" for s in sessions]
        
        try:
            curr_idx = session_ids.index(st.session_state.session_id)
        except ValueError:
            curr_idx = 0
            
        selected_sid = st.selectbox(
            "Select conversation thread:",
            options=session_ids,
            format_func=lambda x: session_labels[session_ids.index(x)],
            index=curr_idx,
            label_visibility="collapsed"
        )
        if selected_sid != st.session_state.session_id:
            st.session_state.session_id = selected_sid
            st.rerun()
            
    if st.button("➕ Start New Session", use_container_width=True):
        st.session_state.session_id = str(uuid.uuid4())
        create_session(st.session_state.session_id)
        st.success("New session started! 🎈")
        st.rerun()

# Retrieve Current Session Info
active_session = get_session(st.session_state.session_id)
if not active_session:
    create_session(st.session_state.session_id)
    active_session = get_session(st.session_state.session_id)

curr_level = active_session["current_level"]
curr_mode = active_session["current_mode"]
curr_topic = active_session["active_topic"]

# ===================== KIDS PLAYROOM CUSTOM STYLING =====================
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Fredoka+One&family=Nunito:wght@400;600;700&display=swap');
    
    .stApp {
        background: linear-gradient(135deg, #FFF9E6 0%, #E8F5E9 100%);
        font-family: 'Nunito', sans-serif;
    }
    
    .kids-title {
        font-family: 'Fredoka One', sans-serif;
        color: #FF7043;
        text-align: center;
        font-size: 40px;
        margin-bottom: 2px;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.05);
    }
    .kids-subtitle {
        font-family: 'Nunito', sans-serif;
        color: #78909C;
        text-align: center;
        font-size: 18px;
        margin-bottom: 25px;
    }
    
    /* Chat bubble styles */
    .bubble-container {
        display: flex;
        align-items: flex-end;
        margin-bottom: 16px;
    }
    .bubble-container.user {
        justify-content: flex-end;
    }
    .bubble-container.assistant {
        justify-content: flex-start;
    }
    
    .chat-bubble {
        max-width: 70%;
        padding: 14px 20px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.05);
        font-size: 18px;
        line-height: 1.4;
    }
    
    .chat-bubble.user {
        background-color: #E3F2FD;
        color: #0D47A1;
        border-radius: 20px 20px 0px 20px;
        border: 2px solid #BBDEFB;
    }
    
    .chat-bubble.assistant {
        background-color: #FFFde7;
        color: #5D4037;
        border-radius: 20px 20px 20px 0px;
        border: 2px solid #FFF59D;
    }
    
    .avatar {
        font-size: 38px;
        user-select: none;
    }
    .avatar.left {
        margin-right: 12px;
    }
    .avatar.right {
        margin-left: 12px;
    }
    
    /* Custom button styling */
    div.stButton > button {
        border-radius: 30px;
        border: 3px solid #FFF59D;
        background: #FFF9C4;
        color: #5D4037;
        font-weight: bold;
        font-size: 16px;
        font-family: 'Fredoka One', sans-serif;
        padding: 12px 24px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        transition: all 0.2s ease-in-out;
    }
    div.stButton > button:hover {
        background-color: #FFF59D;
        border-color: #FBC02D;
        transform: scale(1.05);
        color: #5D4037;
    }
    div.stButton > button:active {
        transform: scale(0.95);
    }
    </style>
    """, 
    unsafe_allow_html=True
)

st.markdown('<h1 class="kids-title">🧸 Learn English with Barnaby!</h1>', unsafe_allow_html=True)
st.markdown(
    f'<p class="kids-subtitle">Your buddy is ready to talk about <b>{curr_topic}</b>! 🎈</p>', 
    unsafe_allow_html=True
)

# Display Chat History
chat_container = st.container()
history = get_chat_history(st.session_state.session_id, limit=20)

with chat_container:
    if not history:
        st.markdown(
            """
            <div style="background-color: rgba(255,255,255,0.7); border-radius: 15px; border: 2px dashed #BDBDBD; padding: 25px; text-align: center; margin: 20px 0;">
                <span style="font-size: 50px;">🧸</span>
                <h3 style="margin-top: 10px; color: #455A64;">Hello there! I'm Barnaby, your English buddy!</h3>
                <p style="color: #78909C; font-size: 16px;">Say hello or click one of the fun bubbles below to start chatting!</p>
            </div>
            """, 
            unsafe_allow_html=True
        )
    else:
        for msg in history:
            if msg["role"] == "user":
                st.markdown(
                    f"""
                    <div class="bubble-container user">
                        <div class="chat-bubble user">{msg["content"]}</div>
                        <div class="avatar right">👶</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            else:
                st.markdown(
                    f"""
                    <div class="bubble-container assistant">
                        <div class="avatar left">🧸</div>
                        <div class="chat-bubble assistant">{msg["content"]}</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

st.markdown("<br>", unsafe_allow_html=True)

# Quick Response Suggestions
st.markdown("<p style='text-align: center; color: #78909C; font-weight: bold; margin-bottom: 8px;'>Choose a quick reply:</p>", unsafe_allow_html=True)

quick_options = [
    ("Hello Barnaby! 🧸", "Hi Barnaby! 🧸"),
    ("Learn a word! 🍎", f"Let's learn a word about {curr_topic}! 🍎"),
    ("Tell a riddle! 🧠", "Tell me a fun riddle! 🧠"),
    ("I did great! ✨", "I did a good job! Thank you!")
]

suggestion_clicked = None
col1, col2, col3, col4 = st.columns(4)
with col1:
    if st.button(quick_options[0][0], use_container_width=True):
        suggestion_clicked = quick_options[0][1]
with col2:
    if st.button(quick_options[1][0], use_container_width=True):
        suggestion_clicked = quick_options[1][1]
with col3:
    if st.button(quick_options[2][0], use_container_width=True):
        suggestion_clicked = quick_options[2][1]
with col4:
    if st.button(quick_options[3][0], use_container_width=True):
        suggestion_clicked = quick_options[3][1]

# Chat Input
chat_input = st.chat_input("Type your message here to talk to Barnaby...")

user_message = None
if chat_input:
    user_message = chat_input
elif suggestion_clicked:
    user_message = suggestion_clicked

if user_message:
    # 1. Log user's message
    log_chat_message(
        session_id=st.session_state.session_id,
        role="user",
        content=user_message,
        level_at_turn=curr_level,
        mode_at_turn=curr_mode,
        topic_at_turn=curr_topic
    )
    
    # 2. Render user message immediately
    st.markdown(
        f"""
        <div class="bubble-container user">
            <div class="chat-bubble user">{user_message}</div>
            <div class="avatar right">👶</div>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # 3. Stream response directly to child
    start_time = time.time()
    ttft = None
    
    placeholder = st.empty()
    bot_reply = ""
    
    placeholder.markdown(
        """
        <div class="bubble-container assistant">
            <div class="avatar left">🧸</div>
            <div class="chat-bubble assistant">🧸 ✍️ ...</div>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    try:
        stream_gen = st.session_state.parent_agent.handle_user_turn(
            session_id=st.session_state.session_id,
            user_input=user_message,
            level=curr_level,
            mode=curr_mode,
            topic=curr_topic,
            stream=True
        )
        for chunk in stream_gen:
            if ttft is None:
                ttft = time.time() - start_time
            bot_reply += chunk
            placeholder.markdown(
                f"""
                <div class="bubble-container assistant">
                    <div class="avatar left">🧸</div>
                    <div class="chat-bubble assistant">{bot_reply} ▌</div>
                </div>
                """,
                unsafe_allow_html=True
            )
    except Exception as e:
        bot_reply = f"Oh, I'm a bit sleepy right now! 🧸 Can you say that again? (Error: {str(e)})"
        
    if ttft is None:
        ttft = time.time() - start_time
        
    placeholder.markdown(
        f"""
        <div class="bubble-container assistant">
            <div class="avatar left">🧸</div>
            <div class="chat-bubble assistant">{bot_reply}</div>
        </div>
        """,
        unsafe_allow_html=True
    )
        
    st.rerun()
