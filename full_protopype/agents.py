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
    temperature=0.7, 
    max_tokens=65, 
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
    """The tutor chatbot sub-agent with tools (FAISS RAG and Web Search)."""
    def __init__(self, vector_db: FAISS = vector_db):
        self.vector_db = vector_db
        self.llm = llm_chat
        
    def route_query(self, query: str) -> str:
        """Determines the appropriate tool based on query keyword matching."""
        query_lower = query.lower()
        
        # Classroom books topic/character keywords
        book_keywords = {
            "sam", "lily", "balloon", "frog", "log", "senses", "sight", "smell", "taste", "hearing", "touch",
            "oak", "tree", "leo", "mia", "rusty", "box", "stones", "leaves", "autumn", "bee", "nectar", "honey",
            "maya", "telescope", "astronomy", "orion", "nebula", "meteor", "betelgeuse", "rigel", "solar", 
            "system", "planets", "mercury", "venus", "mars", "earth", "jupiter", "saturn", "uranus", "neptune",
            "book", "story", "poem", "class 1", "class 2", "class 3", "activities", "quiz", "chapter"
        }
        
        words = re.findall(r'[a-z]+', query_lower)
        if any(w in book_keywords for w in words):
            return "RAG"
            
        # Check for general fact questions to route to Tavily Web Search
        question_words = ["why", "how", "what", "where", "who", "when", "tell me", "fact", "facts", "explain", "is it", "search", "find"]
        if any(query_lower.startswith(qw) or f" {qw} " in f" {query_lower} " for qw in question_words):
            return "WebSearch"
            
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
        elif tool == "WebSearch":
            context = self.run_web_search(user_input)
            reference = "Web Search"
            
        return tool, context, reference
        
    def run_web_search(self, query: str) -> str:
        """Invokes Tavily API directly for search results."""
        try:
            api_key = os.getenv("TAVILY_API") or os.getenv("TAVILY_API_KEY") or "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"
            response = requests.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": api_key,
                    "query": query,
                    "search_depth": "basic",
                    "max_results": 2
                },
                timeout=4.0
            )
            if response.status_code == 200:
                results = response.json().get("results", [])
                search_texts = []
                for r in results:
                    search_texts.append(f"Title: {r.get('title')}\nContent: {r.get('content')}")
                return "Web Search Context:\n" + "\n\n".join(search_texts)
            return "Web search is currently unavailable."
        except Exception as e:
            return f"Web search error: {str(e)}"
            
    def _build_system_prompt(self, level: str, mode: str, topic: str, context: str) -> str:
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
        
        system_prompt = (
            "You are an empathetic, delightful AI English tutor named Barnaby the Bear 🧸 for children under 7.\n"
            "Keep messages EXTREMELY short (1-2 sentences max, under 20 words). Never write long responses. This is critical for latency.\n\n"
            f"Level Instructions: {level_instructions.get(level, level_instructions['L1'])}\n"
            f"Mode Task: {mode_instructions.get(mode, mode_instructions['Conversation'])}\n\n"
        )
        
        if context:
            system_prompt += f"--- CONTEXT INFO ---\nUse the following facts if relevant to answer the child's query:\n{context}\n---------------------\n\n"
            
        system_prompt += (
            "CRITICAL SAFETY RULE:\n"
            "If the Child's input talks about unsafe topics (medical advice, hacking, violence, cyber-security, explicit material, or bullying), "
            "you MUST immediately pivot and deflect by saying: 'Oh, let's play a fun game instead! 🎈 Can you tell me your favorite animal, or should we sing the ABC song?'"
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
    detected_mood: str = Field(description="The child's emotional state: Happy, Sad, Frustrated, Bored, Energetic.")
    recommended_level: str = Field(description="Recommended level: L1, L2, L3.")
    recommended_mode: str = Field(description="Recommended mode: Learning, Conversation, Engagement, Support.")
    recommended_topic: str = Field(description="Suggested learning topic. If child has new interests, output them. Otherwise, repeat the current topic.")

def run_background_evaluation_v2(session_id: str, user_input: str, response: str, chat_log_id: int):
    """Asynchronous background psychologist auditing."""
    evaluator_prompt = ChatPromptTemplate.from_messages([
        ("system", (
            "You are a child safety monitor and a child psychologist auditing a tutoring session.\n"
            "Analyze the Child's input and the Tutor's response.\n"
            "Determine:\n"
            "1. Whether the Child's input was safe (is_safe = False if medical, hacking, sexual, or abusive/aggressive content).\n"
            "2. The Child's emotional state (mood: Happy, Sad, Frustrated, Bored, Energetic).\n"
            "3. The recommended mode for subsequent turns (Support if sad/frustrated, Engagement if bored, Learning if responsive, Conversation if casual).\n"
            "4. The recommended level based on language capability (L1: letters/sounds, L2: vocabulary/short phrases, L3: simple full sentences).\n"
            "5. The recommended topic. If the child shows interest in something specific, suggest a corresponding topic. Otherwise, keep it the same."
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
            "response": clean_response
        })
        
        # Save evaluation to chat log
        update_chat_message_bg_eval(
            chat_log_id=chat_log_id,
            evaluated_level=analysis.recommended_level,
            evaluated_mode=analysis.recommended_mode,
            evaluated_mood=analysis.detected_mood,
            is_safe=analysis.is_safe
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
            is_safe=True
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
            self.start_background_audit(thread_id, user_input, response, log_id)
            
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
        self.start_background_audit(thread_id, user_input, response_text, log_id)

    def start_background_audit(self, session_id: str, user_input: str, response: str, log_id: int):
        """Spawns an asynchronous thread to perform psychologist evaluations."""
        audit_thread = threading.Thread(
            target=run_background_evaluation_v2,
            args=(session_id, user_input, response, log_id),
            daemon=True
        )
        audit_thread.start()
