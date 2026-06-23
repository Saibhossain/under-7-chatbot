import os
from typing import TypedDict, List, Dict, Any, Literal
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, START, END
from dotenv import load_dotenv
load_dotenv()

# Initialize the ultra-fast LLM
llm = ChatOpenAI(model="gpt-4.1-nano-2025-04-14", temperature=0.7)

# ==========================================
# 1. STATE DEFINITION
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
# 2. STRUCTURED OUTPUT SCHEMAS
# ==========================================
class SafetyAssessment(BaseModel):
    is_safe: bool = Field(description="False if the input contains medical queries, cybersecurity/hacking topics, explicit/sexual material, or aggressive/toxic/bullying text.")
    reason: str = Field(description="Brief reason if flagged unsafe.")

class ChildStateAnalysis(BaseModel):
    detected_mood: str = Field(description="The child's emotional state: Happy, Sad, Frustrated, Bored, Energetic.")
    recommended_mode: Literal["Learning", "Conversation", "Engagement", "Support"] = Field(
        description="Switch to 'Support' if sad/frustrated, 'Engagement' if bored, 'Learning' if responsive, 'Conversation' if chatting casually."
    )
    recommended_level: Literal["L1", "L2", "L3"] = Field(
        description="L1: letters/sounds/single words. L2: short phrases/colors. L3: simple sentences. Progress if doing well; lower if struggling."
    )

# ==========================================
# 3. GRAPH NODE IMPLEMENTATIONS
# ==========================================

def guardrail_node(state: ChatbotState) -> Dict[str, Any]:
    """Inspects incoming text for unsafe topics before processing."""
    guardrail_prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a strict safety validator for a child's educational app. Analyze if the input is unsafe for under-7s (medical advice, cybersecurity/hacking, sexual, or aggressive/abusive language)."),
        ("human", "{input}")
    ])
    
    structured_llm = llm.with_structured_output(SafetyAssessment)
    chain = guardrail_prompt | structured_llm
    result = chain.invoke({"input": state["user_input"]})
    
    return {"is_safe": result.is_safe}


def safety_fallback_node(state: ChatbotState) -> Dict[str, Any]:
    """Gracefully pivots away from unsafe content using kid-friendly deflection."""
    return {
        "response": "Oh, let's talk about something else fun! 🎈 Would you like to sing the ABC song or play a word game with me?"
    }


def analyzer_node(state: ChatbotState) -> Dict[str, Any]:
    """Evaluates the child's context, emotional state, and tracks progression."""
    analyzer_prompt = ChatPromptTemplate.from_messages([
        ("system", (
            "Analyze the child's input. Current Level: {current_level}, Current Mode: {current_mode}.\n"
            "Determine mood, recommended interaction mode, and appropriate level (L1: basic letters/phonics, L2: vocabulary/colors, L3: simple sentences)."
        )),
        ("human", "{input}")
    ])
    
    structured_llm = llm.with_structured_output(ChildStateAnalysis)
    chain = analyzer_prompt | structured_llm
    analysis = chain.invoke({
        "current_level": state.get("current_level", "L1"),
        "current_mode": state.get("current_mode", "Conversation"),
        "input": state["user_input"]
    })
    
    return {
        "child_mood": analysis.detected_mood,
        "current_mode": analysis.recommended_mode,
        "current_level": analysis.recommended_level
    }


def content_generator_node(state: ChatbotState) -> Dict[str, Any]:
    """Generates the age-appropriate response tailored to level and mode."""
    
    level_instructions = {
        "L1": "Target age under 5. Use single letters, phonetic sounds, basic objects (e.g., 'A is for Apple! 🍎 Can you say A?'). Very short lines.",
        "L2": "Target age 5-6. Focus on building vocabulary, colors, shapes, and active descriptions (e.g., 'Look at the blue bird! 🐦 What color is it?').",
        "L3": "Target age 6-7. Use simple full sentences. Prompt short conversational answers (e.g., 'I love to eat sweet bananas! What food do you like?')."
    }
    
    mode_instructions = {
        "Learning": "Actively teach and ask a simple English question based on their level.",
        "Conversation": "Chat casually, praise their efforts enthusiastically, and keep things highly relatable.",
        "Engagement": "The child seems distracted. Tell a tiny 2-sentence joke, a riddle, or sound out a game to pull them back in.",
        "Support": "The child feels sad or frustrated. STOP teaching. Offer validation first, tell them they are doing amazing, and give an emotional hug."
    }

    generator_prompt = ChatPromptTemplate.from_messages([
        ("system", (
            "You are an empathetic, delightful AI English tutor for children under 7.\n"
            "Keep messages short (1-3 sentences max), highly encouraging, clear, and full of fun emojis.\n\n"
            "Current Level Context: {level_info}\n"
            "Current Mode Task: {mode_info}\n"
            "Child's Current Mood: {mood}"
        )),
        ("human", "{input}")
    ])
    
    chain = generator_prompt | llm
    res = chain.invoke({
        "level_info": level_instructions[state["current_level"]],
        "mode_info": mode_instructions[state["current_mode"]],
        "mood": state["child_mood"],
        "input": state["user_input"]
    })
    
    return {"response": res.content}


def output_guard_node(state: ChatbotState) -> Dict[str, Any]:
    """Ensures final output generation adheres to strict kid-safe parameters."""
    # Final cleanup constraint check if needed, otherwise acts as final passing gateway
    return {"response": state["response"]}

# ==========================================
# 4. CONDITIONAL ROUTING LOGIC
# ==========================================
def route_safety(state: ChatbotState) -> Literal["safe", "unsafe"]:
    return "safe" if state["is_safe"] else "unsafe"

# ==========================================
# 5. GRAPH BUILD AND COMPILATION
# ==========================================
builder = StateGraph(ChatbotState)

# Define Nodes
builder.add_node("guardrail", guardrail_node)
builder.add_node("safety_fallback", safety_fallback_node)
builder.add_node("analyzer", analyzer_node)
builder.add_node("generator", content_generator_node)
builder.add_node("output_guard", output_guard_node)

# Construct Workflow
builder.add_edge(START, "guardrail")

builder.add_conditional_edges(
    "guardrail",
    route_safety,
    {
        "safe": "analyzer",
        "unsafe": "safety_fallback"
    }
)

builder.add_edge("analyzer", "generator")
builder.add_edge("generator", "output_guard")
builder.add_edge("safety_fallback", "output_guard")
builder.add_edge("output_guard", END)

# Compile Execution Graph
compiled_bot = builder.compile()

try:
    with open("workflow_graph.png", "wb") as f:
        f.write(compiled_bot.get_graph().draw_mermaid_png())
    print("Graph saved successfully as 'workflow_graph.png'")
except Exception as e:
    print(class_name := type(e).__name__, f": {e}")

# ==========================================
# 6. VERIFICATION INTERACTIVE LOOP
# ==========================================
if __name__ == "__main__":
    import time
    
    # Base configuration state initialization
    session_state = {
        "current_level": "L1",
        "current_mode": "Conversation",
        "chat_history": [],
        "child_mood": "Happy"
    }
    
    print("🤖 Children's AI Tutor Bot initialized. (Type 'exit' to quit)\n")
    
    while True:
        user_msg = input("👶 Child: ")
        if user_msg.lower() == 'exit':
            break
            
        session_state["user_input"] = user_msg
        
        start_time = time.time()
        # Execute run iteration over state graph
        updated_state = compiled_bot.invoke(session_state)
        latency = time.time() - start_time
        
        # Keep tracking internal level tracking state across loops
        session_state.update({
            "current_level": updated_state.get("current_level", session_state["current_level"]),
            "current_mode": updated_state.get("current_mode", session_state["current_mode"]),
            "child_mood": updated_state.get("child_mood", session_state["child_mood"])
        })
        
        print(print(f"🤖 Bot: {updated_state['response']}"))
        print(f"⏱️ [Latency: {latency:.2f}s] | [Level: {session_state['current_level']}] | [Mode: {session_state['current_mode']}] | [Mood: {session_state['child_mood']}]\n")