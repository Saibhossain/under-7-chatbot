from typing import Dict, Any, Literal
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from config import llm
from src.state import ChatbotState

class SafetyAssessment(BaseModel):
    is_safe: bool = Field(description="False if input has medical, hacking, sexual, or abusive/aggressive text.")
    reason: str = Field(description="Brief reason.")

def guardrail_node(state: ChatbotState) -> Dict[str, Any]:
    """Inspects incoming messages for safety using structured evaluation."""
    guardrail_prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a strict safety validator for an under-7 kid's app. Flags unsafe topics (medical advice, hacking, sexual content, or aggressive language)."),
        ("human", "{input}")
    ])
    
    structured_llm = llm.with_structured_output(SafetyAssessment)
    chain = guardrail_prompt | structured_llm
    try:
        result = chain.invoke({"input": state["user_input"]})
        return {"is_safe": result.is_safe}
    except Exception:
        # Fail safe if parsing or model errors out
        return {"is_safe": False}

def safety_fallback_node(state: ChatbotState) -> Dict[str, Any]:
    """Graceful deflection for unsafe prompts."""
    fallback_text = "Oh, let's play a fun game instead! 🎈 Can you tell me your favorite animal, or should we sing the ABC song?"
    return {
        "response": fallback_text,
        "chat_history": state.get("chat_history", []) + [
            {"role": "user", "content": state["user_input"]},
            {"role": "assistant", "content": fallback_text}
        ]
    }

def route_safety(state: ChatbotState) -> Literal["safe", "unsafe"]:
    return "safe" if state.get("is_safe", True) else "unsafe"