import os
from typing import TypedDict, List, Dict, Any, Literal
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from dotenv import load_dotenv

load_dotenv()

# ==========================================
# 1. OPTIMIZED LLM INSTANCES
# ==========================================
# Fast LLM for Structural Routing (Temperature 0 = faster, deterministic)
llm_fast = ChatOpenAI(model="gpt-4.1-nano-2025-04-14", temperature=0.0, max_retries=1)

# Chat LLM for Generation (Capped tokens forces early stop = massively reduces latency)
llm_chat = ChatOpenAI(model="gpt-4.1-nano-2025-04-14", temperature=0.7, max_tokens=60, max_retries=1)

# ==========================================
# 2. STATE DEFINITION
# ==========================================
class ChatbotState(TypedDict):
    user_input: str
    response: str
    current_level: Literal["L1", "L2", "L3"]
    current_mode: Literal["Learning", "Conversation", "Engagement", "Support"]
    child_mood: str
    chat_history: List[Dict[str, str]]
    is_safe: bool

# ==========================================
# 3. UNIFIED STRUCTURED SCHEMA
# ==========================================
# We combine safety and mood analysis to cut out an entire network trip!
class UnifiedSafetyAndStateAnalysis(BaseModel):
    is_safe: bool = Field(description="False if the input contains medical queries, cybersecurity/hacking topics, explicit/sexual material, or aggressive/toxic/bullying text.")
    detected_mood: str = Field(description="The child's emotional state: Happy, Sad, Frustrated, Bored, Energetic.")
    recommended_mode: Literal["Learning", "Conversation", "Engagement", "Support"] = Field(
        description="Support if sad/frustrated, Engagement if bored, Learning if responsive, Conversation if chatting casually."
    )
    recommended_level: Literal["L1", "L2", "L3"] = Field(
        description="L1: letters/sounds. L2: short phrases/colors. L3: simple sentences."
    )

# ==========================================
# 4. GRAPH NODE IMPLEMENTATIONS
# ==========================================

def analyzer_node(state: ChatbotState) -> Dict[str, Any]:
    """Single node evaluates Safety, Mood, and Continuity in one hyper-fast call."""
    
    # Grab the last two messages so the analyzer knows the context of short answers like "yes"
    recent_history = state.get("chat_history", [])[-2:]
    history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in recent_history])
    
    analyzer_prompt = ChatPromptTemplate.from_messages([
        ("system", (
            "You are a safety monitor AND a child psychologist.\n"
            "1. Evaluate if the text is safe for under-7s (False if medical, adult, hacking, or abusive).\n"
            "2. Analyze the child's mood, recommended mode, and level.\n"
            "Current Level: {current_level}, Current Mode: {current_mode}.\n\n"
            "CRITICAL RULES:\n"
            "If the child says 'yes' or 'ok', check Recent History. If the Tutor just offered to teach something, keep mode as 'Learning'."
        )),
        ("human", "Recent History:\n{history}\n\nChild's Input: {input}")
    ])
    
    structured_llm = llm_fast.with_structured_output(UnifiedSafetyAndStateAnalysis)
    try:
        analysis = structured_llm.invoke({
            "current_level": state.get("current_level", "L1"),
            "current_mode": state.get("current_mode", "Conversation"),
            "history": history_text if history_text else "None",
            "input": state["user_input"]
        })
        return {
            "is_safe": analysis.is_safe,
            "child_mood": analysis.detected_mood,
            "current_mode": analysis.recommended_mode,
            "current_level": analysis.recommended_level
        }
    except Exception:
        # Failsafe default
        return {
            "is_safe": True, 
            "child_mood": state.get("child_mood", "Happy"),
            "current_mode": state.get("current_mode", "Conversation"),
            "current_level": state.get("current_level", "L1")
        }


def content_generator_node(state: ChatbotState) -> Dict[str, Any]:
    """Generates the age-appropriate response tailored to level and mode."""
    level_instructions = {
        "L1": "Target age under 5. Use single letters, phonetic sounds, basic objects (e.g., 'A is for Apple! 🍎'). Very short lines.",
        "L2": "Target age 5-6. Focus on building vocabulary, colors, shapes, and active descriptions.",
        "L3": "Target age 6-7. Use simple full sentences. Prompt short conversational answers."
    }
    
    mode_instructions = {
        "Learning": "Actively teach and ask a simple English question based on their level.",
        "Conversation": "Chat casually, praise their efforts enthusiastically.",
        "Engagement": "The child seems distracted. Tell a tiny 2-sentence joke or riddle.",
        "Support": "The child feels sad or frustrated. STOP teaching. Validate their feelings."
    }

    history_text = ""
    # Restricted to the last 2 messages for ultra-low latency context
    recent_history = state.get("chat_history", [])[-2:]
    for msg in recent_history:
        speaker = "Child" if msg["role"] == "user" else "Tutor"
        history_text += f"{speaker}: {msg['content']}\n"

    generator_prompt = ChatPromptTemplate.from_messages([
        ("system", (
            "You are an empathetic, delightful AI English tutor for children under 7.\n"
            "Keep messages short (1-3 sentences max), highly encouraging, clear, and full of fun emojis.\n\n"
            "Level Guide: {level_info}\n"
            "Mode Task: {mode_info}\n"
            "Child's Mood: {mood}\n\n"
            "CRITICAL CONTINUITY RULE: Review the Recent History. If you just promised to teach a specific topic, deliver that lesson now.\n\n"
            "--- RECENT CONVERSATION HISTORY ---\n"
            "{history}\n"
            "-----------------------------------"
        )),
        ("human", "{input}")
    ])
    
    chain = generator_prompt | llm_chat
    res = chain.invoke({
        "level_info": level_instructions[state["current_level"]],
        "mode_info": mode_instructions[state["current_mode"]],
        "mood": state["child_mood"],
        "history": history_text if history_text else "No previous history.",
        "input": state["user_input"]
    })
    
    # Save to history internally
    updated_history = state.get("chat_history", []) + [
        {"role": "user", "content": state["user_input"]},
        {"role": "assistant", "content": res.content}
    ]
    
    return {"response": res.content, "chat_history": updated_history}


def safety_fallback_node(state: ChatbotState) -> Dict[str, Any]:
    """Gracefully pivots away from unsafe content."""
    fallback_msg = "Oh, let's talk about something else fun! 🎈 Would you like to sing the ABC song or play a word game with me?"
    
    updated_history = state.get("chat_history", []) + [
        {"role": "user", "content": state["user_input"]},
        {"role": "assistant", "content": fallback_msg}
    ]
    return {"response": fallback_msg, "chat_history": updated_history}


def output_guard_node(state: ChatbotState) -> Dict[str, Any]:
    """Passthrough gateway."""
    return {"response": state["response"]}

# ==========================================
# 5. CONDITIONAL ROUTING LOGIC
# ==========================================
def route_safety(state: ChatbotState) -> Literal["safe", "unsafe"]:
    return "safe" if state.get("is_safe", True) else "unsafe"

# ==========================================
# 6. GRAPH BUILD AND COMPILATION
# ==========================================
builder = StateGraph(ChatbotState)

# Note: 'guardrail_node' has been absorbed into 'analyzer' to cut latency.
builder.add_node("analyzer", analyzer_node)
builder.add_node("generator", content_generator_node)
builder.add_node("safety_fallback", safety_fallback_node)
builder.add_node("output_guard", output_guard_node)

builder.add_edge(START, "analyzer")

builder.add_conditional_edges(
    "analyzer",
    route_safety,
    {
        "safe": "generator",
        "unsafe": "safety_fallback"
    }
)

builder.add_edge("generator", "output_guard")
builder.add_edge("safety_fallback", "output_guard")
builder.add_edge("output_guard", END)

# Attach LangGraph's native Memory Checkpointer
memory_checkpointer = MemorySaver()
compiled_bot = builder.compile(checkpointer=memory_checkpointer)

# try:
#     with open("workflow_graph.png", "wb") as f:
#         f.write(compiled_bot.get_graph().draw_mermaid_png())
#     print("Graph saved successfully as 'workflow_graph.png'")
# except Exception as e:
#     print(class_name := type(e).__name__, f": {e}")

# ==========================================
# 7. VERIFICATION INTERACTIVE LOOP
# ==========================================
if __name__ == "__main__":
    import time
    
    print("🤖 Children's AI Tutor Bot initialized. (Type 'exit' to quit)\n")
    
    # Establish a thread configuration for the Memory Checkpointer
    config = {"configurable": {"thread_id": "cli_test_session"}}
    
    while True:
        user_msg = input("👶 Child: ")
        if user_msg.lower() == 'exit':
            break
            
        # Extract metrics directly from the graph's memory (Single source of truth)
        graph_state = compiled_bot.get_state(config)
        current_data = graph_state.values if graph_state.values else {}
        
        # We ONLY send the user's input and metrics. The MemorySaver handles the chat_history!
        input_payload = {
            "user_input": user_msg,
            "current_level": current_data.get("current_level", "L1"),
            "current_mode": current_data.get("current_mode", "Conversation"),
            "child_mood": current_data.get("child_mood", "Happy")
        }
        
        start_time = time.time()
        updated_state = compiled_bot.invoke(input_payload, config=config)
        latency = time.time() - start_time
        
        # Extract the final values returned from the pipeline
        final_level = updated_state.get('current_level', 'L1')
        final_mode = updated_state.get('current_mode', 'Conversation')
        final_mood = updated_state.get('child_mood', 'Happy')
        
        print(f"🤖 Bot: {updated_state['response']}")
        print(f"⏱️ [Latency: {latency:.2f}s] | [Level: {final_level}] | [Mode: {final_mode}] | [Mood: {final_mood}]\n")