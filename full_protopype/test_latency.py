import os
import sys
import time
import uuid

# Add the full_protopype directory to python path to load the modules
protopype_dir = "/Users/mdsaibhossain/code/python/under-7-chatbot/full_protopype"
if protopype_dir not in sys.path:
    sys.path.insert(0, protopype_dir)

from db import create_session, get_session, get_chat_history, log_chat_message
from llm_utils import generate_chat_response, run_background_evaluation
import threading

def main():
    print("🚀 Starting Latency and Async Background Evaluation Test...")
    
    # Generate test session
    session_id = f"test_{uuid.uuid4().hex[:10]}"
    create_session(session_id, current_level='L1', current_mode='Conversation', active_topic='Fruits')
    print(f"✅ Test session created: {session_id}")
    
    messages = [
        "Hello!",
        "I like apples!",
        "What is your favorite food?"
    ]
    
    for i, user_msg in enumerate(messages):
        session = get_session(session_id)
        print(f"\n--- Turn {i+1} ---")
        print(f"👶 Child: {user_msg}")
        print(f"   Active session state: Level={session['current_level']}, Mode={session['current_mode']}, Topic={session['active_topic']}")
        
        log_chat_message(
            session_id=session_id,
            role="user",
            content=user_msg,
            level_at_turn=session['current_level'],
            mode_at_turn=session['current_mode'],
            topic_at_turn=session['active_topic']
        )
        
        start_time = time.time()
        history = get_chat_history(session_id, limit=5)
        response = generate_chat_response(
            user_input=user_msg,
            history=history,
            level=session['current_level'],
            mode=session['current_mode'],
            topic=session['active_topic']
        )
        latency = time.time() - start_time
        print(f"🤖 Tutor response: {response}")
        print(f"⏱️ Response Latency: {latency:.4f} seconds")
        
        chat_log_id = log_chat_message(
            session_id=session_id,
            role="assistant",
            content=response,
            latency=latency,
            level_at_turn=session['current_level'],
            mode_at_turn=session['current_mode'],
            topic_at_turn=session['active_topic']
        )
        
        # Trigger the background evaluation in a thread
        thread = threading.Thread(
            target=run_background_evaluation,
            args=(session_id, user_msg, response, chat_log_id)
        )
        thread.start()
        
        # Let's wait slightly to let the background thread finish before next turn
        time.sleep(1.5)
        
        # Verify db updates
        updated_session = get_session(session_id)
        updated_history = get_chat_history(session_id, limit=None)
        assistant_log = [l for l in updated_history if l['id'] == chat_log_id][0]
        
        print(f"   Evaluated by AI: {assistant_log['bg_evaluated'] == 1} (Safe={assistant_log['is_safe'] == 1}, Level={assistant_log['evaluated_level']}, Mode={assistant_log['evaluated_mode']})")
        print(f"   Next turn level in DB: {updated_session['current_level']}, Mode in DB: {updated_session['current_mode']}")

    print("\n🎉 Latency test completed successfully.")

if __name__ == "__main__":
    main()

