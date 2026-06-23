from typing import TypedDict, List, Dict, Any, Literal

class ChatbotState(TypedDict):
    user_input: str
    response: str
    current_level: Literal["L1", "L2", "L3"]
    current_mode: Literal["Learning", "Conversation", "Engagement", "Support"]
    child_mood: str
    chat_history: List[Dict[str, str]]
    is_safe: bool