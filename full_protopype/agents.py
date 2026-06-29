import os
import time
import re
import math
import requests
import threading
import warnings
from typing import List, Dict, Tuple
from pydantic import BaseModel, Field

# Suppress Pydantic serialization warnings
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.documents import Document
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from dotenv import load_dotenv

# Database helpers
from db import log_chat_message, get_chat_history, update_chat_message_bg_eval, update_session_bg_eval

load_dotenv()

# Load model configuration
MODEL_NAME = os.getenv("MODEL", "gpt-4o-mini")

# Initialize Chat LLM
llm_chat = ChatOpenAI(
    model=MODEL_NAME, 
    temperature=0.4, 
    max_tokens=45, 
    max_retries=1
)

# Initialize Evaluator LLM (for background parental analysis)
llm_eval = ChatOpenAI(
    model=MODEL_NAME, 
    temperature=0.0, 
    max_retries=1
)

# Initialize OpenAI Embeddings for FAISS
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

# ===================== RAG SYSTEM (FAISS & OPENAI EMBEDDINGS) =====================

def parse_books(file_path: str) -> List[Dict[str, str]]:
    """Parses books.txt into distinct chunks based on stories, poems, and activities."""
    if not os.path.exists(file_path):
        return []
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    sections = []
    current_class = "General English"
    lines = content.split("\n")
    
    current_section_title = "Intro"
    current_section_content = []
    
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("===="):
            continue
        if "CLASS " in line and "CHAPTER" in line:
            current_class = stripped
            continue
        if stripped.startswith("--- ") and stripped.endswith(" ---"):
            # Save previous section if it has content
            if current_section_content:
                sections.append({
                    "class": current_class,
                    "title": current_section_title,
                    "content": "\n".join(current_section_content).strip()
                })
            current_section_title = stripped.replace("---", "").strip()
            current_section_content = []
        else:
            current_section_content.append(line)
            
    # Append the last section
    if current_section_content:
        sections.append({
            "class": current_class,
            "title": current_section_title,
            "content": "\n".join(current_section_content).strip()
        })
        
    return sections

# Load documents and initialize FAISS index locally
books_file_path = os.path.join(os.path.dirname(__file__), "books.txt")
parsed_sections = parse_books(books_file_path)

INDEX_DIR = os.path.join(os.path.dirname(__file__), "faiss_index")
vector_db = None

try:
    if os.path.exists(INDEX_DIR):
        # Load local FAISS index
        vector_db = FAISS.load_local(INDEX_DIR, embeddings, allow_dangerous_deserialization=True)
    else:
        # Build index if not cached
        docs = [
            Document(
                page_content=sec["content"],
                metadata={"title": sec["title"], "class": sec["class"]}
            )
            for sec in parsed_sections
        ]
        if docs:
            vector_db = FAISS.from_documents(docs, embeddings)
            vector_db.save_local(INDEX_DIR)
except Exception as e:
    print(f"Error loading or creating FAISS vector DB: {str(e)}")

# ===================== SUB-AGENT (LEARNING CHATBOT) =====================

class LearningChatbotAgent:
    """The tutor chatbot sub-agent with tools (FAISS RAG)."""
    def __init__(self, vector_db: FAISS = vector_db):
        self.vector_db = vector_db
        self.llm = llm_chat
        
    def route_query(self, query: str) -> str:
        """Determines the appropriate tool based on query keyword matching."""
        # 1. Clean query (normalize apostrophes for typo resilience)
        query_lower = query.lower()
        query_clean = query_lower.replace("'", "").replace("’", "")
        
        # Check for purely conversational / memory / greeting / game queries first
        conversational_keywords = {
            "my favorite", "my name", "my age", "remember", "forget", "clear", "reset", "hello", "hi", 
            "hey", "greetings", "good morning", "good afternoon", "thank you", "thanks", "bye", "goodbye",
            "bored", "im bored", "i am bored", "play", "game", "song", "abc", "how are you", "who are you", 
            "whats up", "changed my mind", "tell me a joke", "tell a joke", "joke", "riddle", "clear my",
            "remove my", "erase"
        }
        if any(kw in query_clean for kw in conversational_keywords):
            return "None"
            
        # 2. Classroom books topic/character keywords (both singular and plural)
        book_keywords = {
            "sam", "lily", "balloon", "balloons", "frog", "frogs", "log", "logs", "sense", "senses", 
            "sight", "smell", "taste", "hearing", "touch", "oak", "tree", "trees", "leo", "mia", 
            "rusty", "box", "boxes", "stone", "stones", "leaf", "leaves", "autumn", "bee", "bees", 
            "nectar", "honey", "maya", "telescope", "telescopes", "astronomy", "orion", "nebula", 
            "nebulas", "meteor", "meteors", "betelgeuse", "rigel", "solar", "system", "systems", 
            "planet", "planets", "mercury", "venus", "mars", "earth", "jupiter", "saturn", "uranus", 
            "neptune", "book", "books", "story", "stories", "poem", "poems", "class 1", "class 2", 
            "class 3", "activities", "quiz", "quizzes", "chapter", "chapters"
        }
        
        words = re.findall(r'[a-z]+', query_lower)
        if any(w in book_keywords for w in words):
            return "RAG"
            
        return "None"
        
    def get_tool_and_context(self, user_input: str) -> Tuple[str, str, str]:
        """Runs the routed tool and retrieves the text context and source reference."""
        tool = self.route_query(user_input)
        context = ""
        reference = ""
        
        if tool == "RAG":
            if self.vector_db:
                try:
                    results = self.vector_db.similarity_search(user_input, k=1)
                    if results:
                        doc = results[0]
                        context = doc.page_content
                        ref_class = doc.metadata.get("class", "Classroom Material")
                        ref_title = doc.metadata.get("title", "Story")
                        reference = f"{ref_class} - {ref_title}"
                except Exception as e:
                    print(f"FAISS search failed: {str(e)}")
            
        return tool, context, reference
            
    def _build_system_prompt(self, level: str, mode: str, topic: str, context: str) -> str:
        level_instructions = {
            "L1": "Target age under 5. Use single letters, phonetic sounds, basic objects (e.g., 'A is for Apple! 🍎'). Keep words extremely short.",
            "L2": "Target age 5-6. Focus on building vocabulary, colors, shapes, and active descriptions.",
            "L3": "Target age 6-7. Use simple full sentences. Prompt short conversational answers."
        }

        # Each mode task now ends with a short SEL nudge, scaled to the rest of the instruction.
        # Support keeps its own full SEL response further below, so it's excluded here to avoid duplicating tone.
        mode_instructions = {
            "Learning": (
                f"Actively teach and ask a simple English question based on the topic '{topic}'. "
                "Keep the child engaged in learning. End with a tiny encouraging note about effort or curiosity "
                "(e.g., 'You're so curious! 🌟')."
            ),
            "Conversation": (
                f"Chat casually and play. If parent specified a topic ({topic}), you can subtly weave it in, but "
                "prioritize a natural, fun chat. Praise their efforts enthusiastically, and notice their feelings "
                "if they share any (e.g., 'That sounds exciting! How did that make you feel?')."
            ),
            "Engagement": (
                "The child seems distracted. Tell a tiny 2-sentence joke or riddle to capture their attention, "
                "matching their level's vocabulary. Keep your tone warm and curious to gently re-invite their focus."
            ),
            "Support": (
                "The child feels sad or frustrated. STOP teaching. Validate their feelings with love and "
                "encouragement. Name the feeling simply if you can (e.g., 'It's okay to feel sad sometimes.')."
            )
        }

        system_prompt = (
            "You are an empathetic, delightful AI English tutor named Barnaby the Bear 🧸 for children under 7.\n"
            "Keep messages EXTREMELY short (1-2 sentences max, under 20 words). Never write long responses. This is critical for latency.\n\n"
            f"Level Instructions: {level_instructions.get(level, level_instructions['L1'])}\n"
            f"Mode Task: {mode_instructions.get(mode, mode_instructions['Conversation'])}\n\n"
            "General SEL reminder: Across every mode, stay warm and encouraging. If the child expresses any feeling "
            "(proud, excited, nervous, sad, frustrated), briefly acknowledge it by name before moving on — this matters "
            "more than finishing the current task.\n\n"
        )

        if context:
            system_prompt += f"--- CONTEXT INFO ---\nUse the following facts if relevant to answer the child's query:\n{context}\n---------------------\n\n"

        system_prompt += (
            "SAFETY RULES:\n"
            "- Unsafe queries (medical advice, hacking, violence, cybersecurity, explicit content): Pivot immediately and say exactly: 'Oh, let's play a fun game instead! 🎈 Can you tell me your favorite animal, or should we sing the ABC song?'\n"
            "- Safe but out-of-scope/advanced queries (full poems, research papers, memory clearance): DO NOT say the game/song pivot. Instead, respond simply matching their level (L1/L2: say 'I don't know that yet! 🎈' or guide to a simple letter/sound/color; L3: explain in 1 simple sentence).\n"
            "- Bullying disclosures: Validate feelings simply, suggest telling a grown-up, and softly return to play. (DO NOT say the game/song pivot).\n"
            "- Self-harm/Distress: Say one caring sentence, urge them to tell a grown-up immediately. (DO NOT say the game/song pivot)."
        )

        return system_prompt
        
    def run_llm(self, user_input: str, history: List[Dict], level: str, mode: str, topic: str, context: str, tool: str) -> str:
        system_prompt = self._build_system_prompt(level, mode, topic, context)
        
        messages = [SystemMessage(content=system_prompt)]
        for msg in history[-6:]:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            else:
                content = msg["content"]
                if "\n\n*📚 Source:" in content:
                    content = content.split("\n\n*📚 Source:")[0]
                messages.append(AIMessage(content=content))
        messages.append(HumanMessage(content=user_input))
        
        try:
            res = self.llm.invoke(messages)
            return res.content
        except Exception as e:
            return f"Oh, I'm a bit sleepy right now! 🧸 Can you say that again? (Error: {str(e)})"
            
    def run_llm_stream(self, user_input: str, history: List[Dict], level: str, mode: str, topic: str, context: str, tool: str):
        system_prompt = self._build_system_prompt(level, mode, topic, context)
        
        messages = [SystemMessage(content=system_prompt)]
        for msg in history[-6:]:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            else:
                content = msg["content"]
                if "\n\n*📚 Source:" in content:
                    content = content.split("\n\n*📚 Source:")[0]
                messages.append(AIMessage(content=content))
        messages.append(HumanMessage(content=user_input))
        
        try:
            for chunk in self.llm.stream(messages):
                yield chunk.content
        except Exception as e:
            yield f"Oh, I'm a bit sleepy right now! 🧸 Can you say that again? (Error: {str(e)})"

# ===================== MAIN AGENT (PARENTAL CONTROL) =====================

class ParentalControlAudit(BaseModel):
    is_safe: bool = Field(description="False if the child's input contains medical queries, cybersecurity/hacking topics, explicit/sexual material, or aggressive/toxic/bullying text.")
    concern_flag: str = Field(description="Concern flag: none, bullying_disclosure, self_harm_or_distress, abuse_disclosure.")
    detected_mood: str = Field(description="The child's emotional state: Happy, Sad, Frustrated, Bored, Energetic, Curious, Confused, Anxious, Neutral.")
    recommended_level: str = Field(description="Recommended level: L1, L2, L3.")
    recommended_mode: str = Field(description="Recommended mode: Learning, Conversation, Engagement, Support.")
    recommended_topic: str = Field(description="Suggested learning topic. If child has new interests, output them. Otherwise, repeat the current topic or return null.")
    sel_quality: str = Field(description="SEL quality audit of Tutor response: good, neutral, missed_opportunity.")

def run_background_evaluation_v2(session_id: str, user_input: str, response: str, chat_log_id: int,
                                   current_level: str = "L1", current_mode: str = "Conversation"):
    """Asynchronous background psychologist auditing with streak tracking."""
    # 1. Fetch recent history for streak tracking
    history_logs = get_chat_history(session_id, limit=4)
    recent_turns_text = ""
    if history_logs:
        for idx, msg in enumerate(history_logs):
            role_name = "Child" if msg["role"] == "user" else "Tutor"
            eval_info = ""
            if msg["role"] == "user" and msg.get("evaluated_mood"):
                eval_info = f" [Audit: Mood={msg['evaluated_mood']}, Level={msg.get('evaluated_level', '')}]"
            # Exclude the current live turn we are analyzing in this run to avoid recursion/circularity
            if msg["content"] == user_input or msg["content"] == response:
                continue
            recent_turns_text += f"- {role_name}: {msg['content']}{eval_info}\n"
    if not recent_turns_text:
        recent_turns_text = "No previous turns in history."

    evaluator_prompt = ChatPromptTemplate.from_messages([
        ("system", (
            "You are a child safety monitor and a child psychologist auditing a tutoring session between an AI "
            "tutor and a child under 7.\n"
            "Analyze the Child's input and the Tutor's response, given the Child's current level and mode.\n\n"
            "Determine the following:\n\n"

            "1. is_safe: False if the Child's input contains medical content, hacking/cybersecurity, sexual or "
            "explicit content, or the Child being aggressive/abusive toward others (e.g., cursing, threats). "
            "Otherwise True. Note: bullying disclosures and self-harm/distress disclosures are NOT safety "
            "violations by the child — they are handled separately in concern_flag below, and should not make "
            "is_safe False on their own.\n\n"

            "2. concern_flag: one of [none, bullying_disclosure, self_harm_or_distress, abuse_disclosure]. Use "
            "bullying_disclosure if the child describes being mocked, excluded, or hurt by a peer. Use "
            "self_harm_or_distress if the child expresses wanting to disappear, not exist, extreme despair, or "
            "self-harm. Use abuse_disclosure if the child describes being hurt, neglected, or mistreated by an "
            "adult or caregiver. Use none otherwise. This flag is independent of is_safe and should be set "
            "whenever applicable, even if is_safe is True.\n\n"

            "3. detected_mood: one of [Happy, Sad, Frustrated, Bored, Energetic, Curious, Confused, Anxious, Neutral]. "
            "Pick the single best match for the child's emotional state in this turn.\n\n"

            "4. recommended_mode: one of [Learning, Conversation, Engagement, Support]. Use this mapping as a "
            "default, but use judgment if context suggests otherwise:\n"
            "   - Support: mood is Sad, Frustrated, Anxious, or concern_flag is not none.\n"
            "   - Engagement: mood is Bored.\n"
            "   - Learning: mood is Curious, Confused, or Energetic and the child is responsive to teaching.\n"
            "   - Conversation: mood is Happy or Neutral and the exchange is casual/social.\n\n"

            "5. recommended_level: one of [L1, L2, L3]. The Child's current level is {current_level}.\n"
            "Use the provided session history to track the child's progress consistency. "
            "Only recommend a level change (L1/L2/L3) if you see a consistent streak/pattern over multiple turns:\n"
            "   - Move up: if the child consistently forms responses exceeding their current level across several turns.\n"
            "   - Move down: if the child consistently struggles or fails to comprehend the current level's complexity across several turns.\n"
            "   - Keep unchanged: if the signal is mixed or it is an isolated turn. Set recommended_level to {current_level}.\n\n"

            "6. recommended_topic: If the child shows clear interest in a specific subject, suggest that topic. "
            "Otherwise, return null to keep the existing topic unchanged.\n\n"

            "7. sel_quality: one of [good, neutral, missed_opportunity]. Audit the Tutor's response itself (not "
            "the child): 'good' if the tutor validated a feeling, named an emotion, or encouraged confidence/"
            "curiosity appropriately; 'neutral' if SEL wasn't relevant this turn and the tutor didn't force it; "
            "'missed_opportunity' if the child expressed an emotion or concern and the Tutor's response ignored "
            "it or moved on too quickly.\n\n"

            "Recent Session History:\n"
            "{recent_turns}\n\n"

            "The Child's current mode going into this turn was {current_mode}; use this only as context for "
            "judging the response, not as a constraint on your recommendation."
        )),
        ("human", "Child's Input: {input}\n\nTutor's Response: {response}")
    ])
    
    # Strip footer source info before auditing
    clean_response = response
    if "\n\n*📚 Source:" in response:
        clean_response = response.split("\n\n*📚 Source:")[0]
        
    try:
        structured_eval_llm = llm_eval.with_structured_output(ParentalControlAudit)
        chain = evaluator_prompt | structured_eval_llm
        analysis = chain.invoke({
            "input": user_input,
            "response": clean_response,
            "current_level": current_level,
            "current_mode": current_mode,
            "recent_turns": recent_turns_text
        })
        
        # Save evaluation to chat log
        update_chat_message_bg_eval(
            chat_log_id=chat_log_id,
            evaluated_level=analysis.recommended_level,
            evaluated_mode=analysis.recommended_mode,
            evaluated_mood=analysis.detected_mood,
            is_safe=analysis.is_safe,
            concern_flag=analysis.concern_flag,
            sel_quality=analysis.sel_quality
        )
        
        # Update session table with evaluation settings
        update_session_bg_eval(
            session_id=session_id,
            level=analysis.recommended_level,
            mode=analysis.recommended_mode,
            mood=analysis.detected_mood,
            active_topic=analysis.recommended_topic
        )
        
    except Exception as e:
        print(f"Background evaluation failed for session {session_id}: {str(e)}")
        # Fallback to save safe defaults
        update_chat_message_bg_eval(
            chat_log_id=chat_log_id,
            evaluated_level="L1",
            evaluated_mode="Conversation",
            evaluated_mood="Happy",
            is_safe=True,
            concern_flag="none",
            sel_quality="neutral"
        )

class ParentalControlAgent:
    """The coordinator agent representing parental control."""
    def __init__(self, sub_agent: LearningChatbotAgent = None):
        self.sub_agent = sub_agent or LearningChatbotAgent()
        
    def handle_user_turn(self, session_id: str, user_input: str, level: str, mode: str, topic: str, stream: bool = False):
        # Persistent memory: thread_id mapped to session_id
        thread_id = session_id
        history = get_chat_history(thread_id, limit=5)
        
        # Tool execution & context retrieval
        tool, context, reference = self.sub_agent.get_tool_and_context(user_input)
        
        if stream:
            return self._stream_and_log(thread_id, user_input, history, level, mode, topic, context, tool, reference)
        else:
            t0 = time.time()
            response = self.sub_agent.run_llm(user_input, history, level, mode, topic, context, tool)
            if tool == "RAG" and reference:
                response += f"\n\n*📚 Source: {reference}*"
            latency = time.time() - t0
            
            # Log turn to database
            log_id = log_chat_message(
                session_id=thread_id,
                role="assistant",
                content=response,
                latency=latency,
                level_at_turn=level,
                mode_at_turn=mode,
                topic_at_turn=topic,
                tools_used=tool,
                agent_name="LearningChatbotAgent"
            )
            
            # Run background diagnostics asynchronously
            self.start_background_audit(thread_id, user_input, response, log_id, level, mode)
            
            return response, latency, tool
            
    def _stream_and_log(self, thread_id: str, user_input: str, history: List[Dict], level: str, mode: str, topic: str, context: str, tool: str, reference: str):
        t0 = time.time()
        ttft = None
        full_response = []
        
        generator = self.sub_agent.run_llm_stream(user_input, history, level, mode, topic, context, tool)
        for chunk in generator:
            if ttft is None:
                ttft = time.time() - t0
            full_response.append(chunk)
            yield chunk
            
        # Append source reference markdown natively at the end of streaming
        if tool == "RAG" and reference:
            ref_footer = f"\n\n*📚 Source: {reference}*"
            full_response.append(ref_footer)
            yield ref_footer
            
        latency = time.time() - t0
        response_text = "".join(full_response)
        
        # Log tutor message to DB
        log_id = log_chat_message(
            session_id=thread_id,
            role="assistant",
            content=response_text,
            latency=latency,
            level_at_turn=level,
            mode_at_turn=mode,
            topic_at_turn=topic,
            tools_used=tool,
            agent_name="LearningChatbotAgent"
        )
        
        # Run background diagnostics asynchronously
        self.start_background_audit(thread_id, user_input, response_text, log_id, level, mode)

    def start_background_audit(self, session_id: str, user_input: str, response: str, log_id: int, level: str = "L1", mode: str = "Conversation"):
        """Spawns an asynchronous thread to perform psychologist evaluations."""
        audit_thread = threading.Thread(
            target=run_background_evaluation_v2,
            args=(session_id, user_input, response, log_id, level, mode),
            daemon=True
        )
        audit_thread.start()
