import os
import time
from typing import Dict, Any, Literal, List
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv

# Import database functions
from db import update_chat_message_bg_eval, update_session_bg_eval

load_dotenv()

# Model Config
MODEL_NAME = os.getenv("MODEL", "gpt-4o-mini")

# Optimize LLM parameters for speed and cost
# Chat LLM: capped tokens and temperature for responsive conversational outputs
llm_chat = ChatOpenAI(
    model=MODEL_NAME, 
    temperature=0.7, 
    max_tokens=65, 
    max_retries=1
)

# Evaluator LLM: temperature 0.0 for consistent deterministic outputs
llm_eval = ChatOpenAI(
    model=MODEL_NAME, 
    temperature=0.0, 
    max_retries=1
)

# Pydantic schema for background state evaluation
class ChildStateAnalysis(BaseModel):
    is_safe: bool = Field(description="False if the child's input contains medical queries, cybersecurity/hacking topics, explicit/sexual material, or aggressive/toxic/bullying text.")
    detected_mood: str = Field(description="The child's emotional state: Happy, Sad, Frustrated, Bored, Energetic.")
    recommended_mode: Literal["Learning", "Conversation", "Engagement", "Support"] = Field(
        description="Support if sad/frustrated, Engagement if bored/distracted, Learning if ready to study, Conversation for casual chat."
    )
    recommended_level: Literal["L1", "L2", "L3"] = Field(
        description="L1: letters/sounds. L2: short phrases/colors. L3: simple sentences."
    )

def generate_chat_response(
    user_input: str,
    history: List[Dict[str, str]],
    level: str,
    mode: str,
    topic: str
) -> str:
    """
    Generates a child-friendly response in a single, highly-optimized LLM call.
    Includes safety guidelines directly in the system prompt to avoid a separate guardrail call.
    """
    level_instructions = {
        "L1": "Target age under 5. Use single letters, phonetic sounds, basic objects (e.g., 'A is for Apple! 🍎'). Keep words extremely short.",
        "L2": "Target age 5-6. Focus on building vocabulary, colors, shapes, and active descriptions.",
        "L3": "Target age 6-7. Use simple full sentences. Prompt short conversational answers."
    }
    
    mode_instructions = {
        "Learning": f"Actively teach and ask a simple English question based on the topic '{topic}'. Keep the child engaged in learning.",
        "Conversation": f"Chat casually and play. If parent specified a topic ({topic}), you can subtly weave it in, but prioritize a natural, fun chat. Praise their efforts enthusiastically.",
        "Engagement": "The child seems distracted. Tell a tiny 2-sentence joke or riddle to capture their attention.",
        "Support": "The child feels sad or frustrated. STOP teaching. Validate their feelings with love and encouragement."
    }
    
    # Format recent history for prompt context (limit to last 4 messages to save context processing time)
    history_text = ""
    for msg in history[-4:]:
        speaker = "Child" if msg["role"] == "user" else "Tutor"
        history_text += f"{speaker}: {msg['content']}\n"

    system_prompt = (
        "You are an empathetic, delightful AI English tutor named Barnaby the Bear 🧸 for children under 7.\n"
        "Keep messages EXTREMELY short (1-2 sentences max, under 20 words). Never write long responses. This is critical for latency.\n\n"
        "Level Instructions: {level_info}\n"
        "Mode Task: {mode_info}\n\n"
        "CRITICAL SAFETY RULE:\n"
        "If the Child's input talks about unsafe topics (medical advice, hacking, violence, cyber-security, explicit material, or bullying), "
        "you MUST immediately pivot and deflect by saying: 'Oh, let's play a fun game instead! 🎈 Can you tell me your favorite animal, or should we sing the ABC song?'\n\n"
        "--- RECENT CONVERSATION HISTORY ---\n"
        "{history}\n"
        "-----------------------------------"
    )

    prompt_template = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{input}")
    ])
    
    chain = prompt_template | llm_chat
    
    try:
        response = chain.invoke({
            "level_info": level_instructions.get(level, level_instructions["L1"]),
            "mode_info": mode_instructions.get(mode, mode_instructions["Conversation"]),
            "history": history_text if history_text else "No previous history.",
            "input": user_input
        })
        return response.content
    except Exception as e:
        return f"Oh, I'm a bit sleepy right now! 🧸 Can you say that again? (Error: {str(e)})"

def stream_chat_response(
    user_input: str,
    history: List[Dict[str, str]],
    level: str,
    mode: str,
    topic: str
):
    """
    Streams the response from the LLM token-by-token for ultra-low perceived latency.
    """
    level_instructions = {
        "L1": "Target age under 5. Use single letters, phonetic sounds, basic objects (e.g., 'A is for Apple! 🍎'). Keep words extremely short.",
        "L2": "Target age 5-6. Focus on building vocabulary, colors, shapes, and active descriptions.",
        "L3": "Target age 6-7. Use simple full sentences. Prompt short conversational answers."
    }
    
    mode_instructions = {
        "Learning": f"Actively teach and ask a simple English question based on the topic '{topic}'. Keep the child engaged in learning.",
        "Conversation": f"Chat casually and play. If parent specified a topic ({topic}), you can subtly weave it in, but prioritize a natural, fun chat. Praise their efforts enthusiastically.",
        "Engagement": "The child seems distracted. Tell a tiny 2-sentence joke or riddle to capture their attention.",
        "Support": "The child feels sad or frustrated. STOP teaching. Validate their feelings with love and encouragement."
    }
    
    history_text = ""
    for msg in history[-4:]:
        speaker = "Child" if msg["role"] == "user" else "Tutor"
        history_text += f"{speaker}: {msg['content']}\n"

    system_prompt = (
        "You are an empathetic, delightful AI English tutor named Barnaby the Bear 🧸 for children under 7.\n"
        "Keep messages EXTREMELY short (1-2 sentences max, under 20 words). Never write long responses. This is critical for latency.\n\n"
        "Level Instructions: {level_info}\n"
        "Mode Task: {mode_info}\n\n"
        "CRITICAL SAFETY RULE:\n"
        "If the Child's input talks about unsafe topics (medical advice, hacking, violence, cyber-security, explicit material, or bullying), "
        "you MUST immediately pivot and deflect by saying: 'Oh, let's play a fun game instead! 🎈 Can you tell me your favorite animal, or should we sing the ABC song?'\n\n"
        "--- RECENT CONVERSATION HISTORY ---\n"
        "{history}\n"
        "-----------------------------------"
    )

    prompt_template = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{input}")
    ])
    
    chain = prompt_template | llm_chat
    
    try:
        for chunk in chain.stream({
            "level_info": level_instructions.get(level, level_instructions["L1"]),
            "mode_info": mode_instructions.get(mode, mode_instructions["Conversation"]),
            "history": history_text if history_text else "No previous history.",
            "input": user_input
        }):
            yield chunk.content
    except Exception as e:
        yield f"Oh, I'm a bit sleepy right now! 🧸 Can you say that again? (Error: {str(e)})"

def run_background_evaluation(
    session_id: str,
    user_input: str,
    response: str,
    chat_log_id: int
):
    """
    Runs in a background thread.
    Uses a second structured LLM call to evaluate the child's mood, recommended level, mode, and safety status.
    Updates the database with findings, adjusting session level/mode for future turns (if parent overrides are off).
    """
    # Create the prompt for the psychologist evaluation
    evaluator_prompt = ChatPromptTemplate.from_messages([
        ("system", (
            "You are a child safety monitor and a child psychologist auditing a tutoring session.\n"
            "Analyze the Child's input and the Tutor's response.\n"
            "Determine:\n"
            "1. Whether the Child's input was safe (is_safe = False if medical, hacking, sexual, or abusive/aggressive content).\n"
            "2. The Child's emotional state (mood: Happy, Sad, Frustrated, Bored, Energetic).\n"
            "3. The recommended mode for subsequent turns (Support if sad/frustrated, Engagement if bored, Learning if responsive, Conversation if casual).\n"
            "4. The recommended level based on language capability (L1: letters/sounds, L2: vocabulary/short phrases, L3: full sentences)."
        )),
        ("human", "Child's Input: {input}\n\nTutor's Response: {response}")
    ])
    
    structured_eval_llm = llm_eval.with_structured_output(ChildStateAnalysis)
    chain = evaluator_prompt | structured_eval_llm
    
    start_eval_time = time.time()
    try:
        analysis = chain.invoke({
            "input": user_input,
            "response": response
        })
        eval_latency = time.time() - start_eval_time
        
        # Save evaluation to chat log
        update_chat_message_bg_eval(
            chat_log_id=chat_log_id,
            evaluated_level=analysis.recommended_level,
            evaluated_mode=analysis.recommended_mode,
            evaluated_mood=analysis.detected_mood,
            is_safe=analysis.is_safe
        )
        
        # Update session table with the background evaluation
        update_session_bg_eval(
            session_id=session_id,
            level=analysis.recommended_level,
            mode=analysis.recommended_mode,
            mood=analysis.detected_mood
        )
        
    except Exception as e:
        # Fallback in case of LLM error in background
        print(f"Background evaluation failed for session {session_id}: {str(e)}")
        update_chat_message_bg_eval(
            chat_log_id=chat_log_id,
            evaluated_level="L1",
            evaluated_mode="Conversation",
            evaluated_mood="Happy",
            is_safe=True
        )
