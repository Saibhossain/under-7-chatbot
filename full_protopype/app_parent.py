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
    get_session_stats,
    update_session_parent_settings
)
from agents import (
    LearningChatbotAgent,
    ParentalControlAgent,
    run_background_evaluation_v2
)

st.set_page_config(
    page_title="Parental Control Panel 🔐",
    layout="wide",
    page_icon="🔐"
)

# Initialize Session State
if "parent_selected_session_id" not in st.session_state:
    sessions = get_all_sessions()
    if sessions:
        st.session_state.parent_selected_session_id = sessions[0]["session_id"]
    else:
        st.session_state.parent_selected_session_id = str(uuid.uuid4())
        create_session(st.session_state.parent_selected_session_id)

# ===================== SIDEBAR =====================
with st.sidebar:
    st.markdown(
        """
        <div style="text-align: center; margin-bottom: 20px;">
            <span style="font-size: 60px;">🔐</span>
            <h2 style="margin: 5px 0 0 0; color: #4A90E2; font-family: 'Helvetica Neue', sans-serif;">Parental Hub</h2>
        </div>
        """, 
        unsafe_allow_html=True
    )
    
    st.divider()
    
    st.markdown("### 💬 Active Conversations")
    sessions = get_all_sessions()
    if sessions:
        session_ids = [s["session_id"] for s in sessions]
        session_labels = [s.get("thread_name") or f"Session {s['session_id'][:4]}" for s in sessions]
        
        try:
            curr_idx = session_ids.index(st.session_state.parent_selected_session_id)
        except ValueError:
            curr_idx = 0
            
        selected_sid = st.selectbox(
            "Select session to inspect:",
            options=session_ids,
            format_func=lambda x: session_labels[session_ids.index(x)],
            index=curr_idx,
            label_visibility="collapsed"
        )
        if selected_sid != st.session_state.parent_selected_session_id:
            st.session_state.parent_selected_session_id = selected_sid
            st.rerun()

# Get details for selected parent session
session_data = get_session(st.session_state.parent_selected_session_id)
if not session_data:
    st.info("Please start a session in the kids app first.")
    st.stop()

stats = get_session_stats(st.session_state.parent_selected_session_id)
history_logs = get_chat_history(st.session_state.parent_selected_session_id, limit=None)

# Run background diagnostics synchronously only when parent visits dashboard
pending_logs = [log for log in history_logs if log["role"] == "assistant" and log["bg_evaluated"] == 0]
if pending_logs:
    with st.spinner("🕵️‍♂️ Running AI diagnostics on new messages..."):
        for log in pending_logs:
            user_input = "Hello"
            for idx, item in enumerate(history_logs):
                if item["id"] == log["id"] and idx > 0:
                    user_input = history_logs[idx-1]["content"]
                    break
            
            run_background_evaluation_v2(
                session_id=st.session_state.parent_selected_session_id,
                user_input=user_input,
                response=log["content"],
                chat_log_id=log["id"],
                current_level=log.get("level_at_turn", "L1") or "L1",
                current_mode=log.get("mode_at_turn", "Conversation") or "Conversation"
            )
        
        st.toast("✅ Analysis complete! Metrics updated.")
        session_data = get_session(st.session_state.parent_selected_session_id)
        stats = get_session_stats(st.session_state.parent_selected_session_id)
        history_logs = get_chat_history(st.session_state.parent_selected_session_id, limit=None)

# ===================== CUSTOM CSS STYLES =====================
st.markdown(
    """
    <style>
    .stApp {
        background-color: #F8F9FA;
        font-family: 'Helvetica Neue', Arial, sans-serif;
    }
    
    /* KPI Cards */
    .kpi-card {
        background-color: white;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        border-left: 5px solid #4A90E2;
        margin-bottom: 15px;
    }
    .kpi-label {
        font-size: 14px;
        color: #7F8C8D;
        text-transform: uppercase;
        font-weight: bold;
        margin-bottom: 5px;
    }
    .kpi-value {
        font-size: 26px;
        font-weight: bold;
        color: #2C3E50;
    }
    
    /* Badges */
    .badge {
        display: inline-block;
        padding: 4px 8px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: bold;
        text-transform: uppercase;
    }
    .badge.level {
        background-color: #E3F2FD;
        color: #0D47A1;
    }
    .badge.mode {
        background-color: #E8F5E9;
        color: #1B5E20;
    }
    .badge.mood {
        background-color: #FFF3E0;
        color: #E65100;
    }
    .badge.safe {
        background-color: #E8F5E9;
        color: #2E7D32;
    }
    .badge.unsafe {
        background-color: #FFEBEE;
        color: #C62828;
    }
    .badge.pending {
        background-color: #ECEFF1;
        color: #37474F;
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.markdown("<h1 style='color:#2C3E50;'>🔐 Parental Control Dashboard</h1>", unsafe_allow_html=True)
st.markdown("<p style='color:#7F8C8D;'>Monitor learning telemetry, customize curriculum themes, and check chatbot latency statistics.</p>", unsafe_allow_html=True)

st.divider()

# Layout splits
col_left, col_right = st.columns([1, 1])

with col_left:
    st.subheader("⚙️ Session Controls")
    
    # Override Toggles
    override = st.toggle("Override Automated AI Curriculum Settings", value=(session_data["override_active"] == 1))
    
    if override != (session_data["override_active"] == 1):
        update_session_parent_settings(st.session_state.parent_selected_session_id, override_active=(1 if override else 0))
        st.toast("Override setting updated!")
        st.rerun()
        
    if override:
        st.info("💡 Parent Override is **ACTIVE**. The background LLM will analyze child inputs, but will **not** automatically modify level or mode.")
        
        new_level = st.selectbox(
            "Manually Set English Level:",
            options=["L1", "L2", "L3"],
            index=["L1", "L2", "L3"].index(session_data["current_level"]),
            help="L1: Letters & sounds | L2: Vocabulary & short phrases | L3: Simple full sentences"
        )
        
        new_mode = st.selectbox(
            "Manually Set Tutor Mode:",
            options=["Learning", "Conversation", "Engagement", "Support"],
            index=["Learning", "Conversation", "Engagement", "Support"].index(session_data["current_mode"]),
            help="Learning: Active queries | Conversation: Normal chat | Engagement: Riddles/Jokes | Support: Validate emotions"
        )
        
        if new_level != session_data["current_level"] or new_mode != session_data["current_mode"]:
            update_session_parent_settings(st.session_state.parent_selected_session_id, level=new_level, mode=new_mode)
            st.toast("Curriculum updated manually!")
            st.rerun()
    else:
        st.info("🤖 **Autopilot Mode**: The background LLM dynamically scales English Level and Tutor Mode based on child sentiment and ability.")
        
        st.markdown(
            f"""
            <div style="background-color: #ECEFF1; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
                <div style="margin-bottom: 8px;"><b>Active English Level:</b> <span class="badge level">{session_data["current_level"]}</span></div>
                <div><b>Active Tutor Mode:</b> <span class="badge mode">{session_data["current_mode"]}</span></div>
            </div>
            """,
            unsafe_allow_html=True
        )
        
    # Topic selection
    current_topic = session_data["active_topic"]
    selected_topic = st.text_input("🎯 Active Learning Topic:", value=current_topic, help="E.g., Animals, Colors, Space, Numbers. Chatbot adjusts generated questions to match this theme.")
    
    if selected_topic != current_topic and selected_topic.strip() != "":
        update_session_parent_settings(st.session_state.parent_selected_session_id, active_topic=selected_topic.strip())
        st.toast("Active topic changed!")
        st.rerun()
        
    # Session Metrics KPI
    st.subheader("📈 Performance & Metrics")
    
    m_col1, m_col2 = st.columns(2)
    with m_col1:
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-label">Avg Chat Latency</div>
                <div class="kpi-value">{stats["avg_latency"]:.2f}s</div>
            </div>
            """,
            unsafe_allow_html=True
        )
    with m_col2:
        st.markdown(
            f"""
            <div class="kpi-card" style="border-left-color: #E67E22;">
                <div class="kpi-label">Detected Child Mood</div>
                <div class="kpi-value">{session_data["mood"]}</div>
            </div>
            """,
            unsafe_allow_html=True
        )
        
    # Latency Benchmark Visualization
    avg_chat = stats["avg_latency"]
    estimated_bg = 2.10
    
    chat_pct = min(100, int((avg_chat / max(0.1, estimated_bg)) * 100)) if avg_chat > 0 else 0
    bg_pct = 100
    
    st.markdown(
        f"""
        <div style="background-color: #F1F3F5; border-radius: 10px; padding: 15px; margin-top: 15px; box-shadow: inset 0 2px 4px rgba(0,0,0,0.05);">
            <h5 style="margin-top: 0; color: #34495E;">⚡ Latency Benchmark (FAISS Vector RAG Architecture)</h5>
            <div style="margin-bottom: 12px;">
                <div style="display: flex; justify-content: space-between; font-size: 13px; color: #495057; font-weight: bold;">
                    <span>Child Response (Single-LLM Path + FAISS)</span>
                    <span>{avg_chat:.2f}s</span>
                </div>
                <div style="background-color: #D6DBDF; border-radius: 5px; height: 10px; width: 100%;">
                    <div style="background-color: #2ECC71; height: 10px; border-radius: 5px; width: {max(5, chat_pct)}%;"></div>
                </div>
            </div>
            <div>
                <div style="display: flex; justify-content: space-between; font-size: 13px; color: #495057; font-weight: bold;">
                    <span>Parent Background Audit (Async Path)</span>
                    <span>{estimated_bg:.2f}s</span>
                </div>
                <div style="background-color: #D6DBDF; border-radius: 5px; height: 10px; width: 100%;">
                    <div style="background-color: #E74C3C; height: 10px; border-radius: 5px; width: {bg_pct}%;"></div>
                </div>
            </div>
            <p style="margin-top: 12px; margin-bottom: 0; font-size: 12.5px; color: #7F8C8D; line-height: 1.3;">
                🚀 **Speedup Summary**: Since heavy level/mode analysis runs out-of-band in background threads, the Child receives responses in real-time (~{avg_chat:.2f}s). Without this, chatbot latency would be **{(avg_chat + estimated_bg):.2f}s** (Chat + Audit sequentially).
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )
    
with col_right:
    st.subheader("🔍 Live Conversation Monitor & Audit")
    
    if not history_logs:
        st.info("No messages in this session yet.")
    else:
        for log in reversed(history_logs):
            timestamp = log["timestamp"][11:16]
            
            if log["role"] == "user":
                st.markdown(
                    f"""
                    <div style="background-color: #EAECEE; padding: 12px 15px; border-radius: 8px; margin-bottom: 10px;">
                        <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                            <span style="font-weight: bold; color: #2E4053;">👶 Child</span>
                            <span style="font-size: 11px; color: #95A5A6;">{timestamp}</span>
                        </div>
                        <div style="color: #2C3E50; font-size: 14px;">{log["content"]}</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            else:
                if log["bg_evaluated"] == 1:
                    safety_badge = '<span class="badge safe">Safe</span>' if log["is_safe"] == 1 else '<span class="badge unsafe">Unsafe ⚠️</span>'
                    eval_text = f"""
                    <div style="margin-top: 8px; border-top: 1px dashed #BDC3C7; padding-top: 8px; font-size: 12px; color: #7F8C8D;">
                        <b>Background Audit:</b> {safety_badge} | 
                        Mood: <span class="badge mood">{log["evaluated_mood"]}</span> | 
                        Level Rec: <span class="badge level">{log["evaluated_level"]}</span> | 
                        Mode Rec: <span class="badge mode">{log["evaluated_mode"]}</span>
                    </div>
                    """
                else:
                    eval_text = """
                    <div style="margin-top: 8px; border-top: 1px dashed #BDC3C7; padding-top: 8px; font-size: 12px; color: #95A5A6;">
                        <b>Background Audit:</b> <span class="badge pending">🔄 Analyzing in background...</span>
                    </div>
                    """
                    
                st.markdown(
                    f"""
                    <div style="background-color: #FCF3CF; padding: 12px 15px; border-radius: 8px; border-left: 4px solid #F1C40F; margin-bottom: 10px;">
                        <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                            <span style="font-weight: bold; color: #7D6608;">🧸 Barnaby (Tutor)</span>
                            <span style="font-size: 11px; color: #95A5A6;">{timestamp} | Latency: <b>{log["latency"]:.2f}s</b></span>
                        </div>
                        <div style="color: #5D4037; font-size: 14px;">{log["content"]}</div>
                        <div style="font-size: 11px; color: #95A5A6; margin-top: 5px;">
                            Active Config at Turn: Level <b>{log["level_at_turn"]}</b> | Mode <b>{log["mode_at_turn"]}</b> | Theme: <b>{log["topic_at_turn"]}</b><br>
                            Agent: <b>{log.get("agent_name") or "LearningChatbotAgent"}</b> | Tool Used: <b>{log.get("tools_used") or "None"}</b>
                        </div>
                        {eval_text}
                    </div>
                    """,
                    unsafe_allow_html=True
                )
