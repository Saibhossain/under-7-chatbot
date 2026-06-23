from typing import Dict, Any, Literal
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from config import llm
from src.state import ChatbotState

class ChildStateAnalysis(BaseModel):
    detected_mood: str = Field(description="Emotional state: Happy, Sad, Frustrated, Bored, Energetic.")
    recommended_mode: Literal["Learning", "Conversation", "Engagement", "Support"] = Field(
        description="Support if sad/frustrated, Engagement if bored/distracted, Learning if ready to study, Conversation for casual chat."
    )
    recommended_level: Literal["L1", "L2", "L3"] = Field(
        description="L1: phonics/letters, L2: vocabulary words, L3: simple sentences."
    )

def analyzer_node(state: ChatbotState) -> Dict[str, Any]:
    """Evaluates mood and mode, taking recent history into account to avoid abrupt topic shifts."""
    
    # Grab the last two messages so the analyzer knows the context of short answers like "yes"
    recent_history = state.get("chat_history", [])[-2:]
    history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in recent_history])
    
    analyzer_prompt = ChatPromptTemplate.from_messages([
        ("system", (
            "Analyze the child's input to determine their mood and the next interaction mode.\n"
            "Current Level: {current_level}, Current Mode: {current_mode}.\n\n"
            "CRITICAL RULES:\n"
            "1. If the child simply says 'yes', 'ok', or agrees, look at the Recent History. If the Tutor just offered to teach something, keep the mode as 'Learning'.\n"
            "2. Do NOT switch to 'Engagement' (riddles/jokes) unless the child explicitly says they are bored, ignores the question entirely, or tries to change the subject."
        )),
        ("human", "Recent History:\n{history}\n\nChild's Input: {input}")
    ])
    
    structured_llm = llm.with_structured_output(ChildStateAnalysis)
    chain = analyzer_prompt | structured_llm
    
    try:
        analysis = chain.invoke({
            "current_level": state.get("current_level", "L1"),
            "current_mode": state.get("current_mode", "Conversation"),
            "history": history_text if history_text else "None",
            "input": state["user_input"]
        })
        return {
            "child_mood": analysis.detected_mood,
            "current_mode": analysis.recommended_mode,
            "current_level": analysis.recommended_level
        }
    except Exception:
        return {
            "child_mood": state.get("child_mood", "Happy"),
            "current_mode": state.get("current_mode", "Conversation"),
            "current_level": state.get("current_level", "L1")
        }

def content_generator_node(state: ChatbotState) -> Dict[str, Any]:
    """Generates localized, kid-safe responses while strictly following previous promises."""
    level_instructions = {
        "L1": "Target age <5. Single letters, phonic sounds, basic fruits/animals.",
        "L2": "Target age 5-6. Vocabulary creation, colors, spatial actions.",
        "L3": "Target age 6-7. Basic complete sentences. Prompt open conversational outputs."
    }
    
    mode_instructions = {
        "Learning": "Deliver an active micro-lesson or simple English query question based strictly on the topic at hand.",
        "Conversation": "Engage playfully, offering high enthusiasm and emojis.",
        "Engagement": "The child seems distracted. Tell a tiny 2-sentence kid's riddle or joke to recapture attention.",
        "Support": "The child is frustrated/sad. Halt lessons immediately. Validate emotions with love and encouragement."
    }

    history_text = ""
    recent_history = state.get("chat_history", [])[-6:]
    for msg in recent_history:
        speaker = "Child" if msg["role"] == "user" else "Tutor"
        history_text += f"{speaker}: {msg['content']}\n"

    generator_prompt = ChatPromptTemplate.from_messages([
        ("system", (
            "You are a loving, animated AI English tutor for children under 7.\n"
            "Keep answers tiny (1-3 sentences max), highly supportive, and easy to read.\n\n"
            "Level Guide: {level_info}\n"
            "Mode Objective: {mode_info}\n"
            "Current Mood: {mood}\n\n"
            "CRITICAL CONTINUITY RULE: Review the Recent History. If you (Tutor) just promised to teach a specific letter, word, or topic, and the Child agreed, you MUST deliver that specific lesson right now. Do not change the subject.\n\n"
            "--- RECENT CONVERSATION HISTORY ---\n"
            "{history}\n"
            "-----------------------------------"
        )),
        ("human", "{input}")
    ])
    
    chain = generator_prompt | llm
    res = chain.invoke({
        "level_info": level_instructions[state["current_level"]],
        "mode_info": mode_instructions[state["current_mode"]],
        "mood": state["child_mood"],
        "history": history_text if history_text else "No previous history.",
        "input": state["user_input"]
    })
    
    updated_history = state.get("chat_history", []) + [
        {"role": "user", "content": state["user_input"]},
        {"role": "assistant", "content": res.content}
    ]
    
    return {
        "response": res.content,
        "chat_history": updated_history
    }