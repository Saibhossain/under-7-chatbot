from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from src.state import ChatbotState
from src.safety import guardrail_node, safety_fallback_node, route_safety
from src.nodes import analyzer_node, content_generator_node

def create_compiled_graph():
    builder = StateGraph(ChatbotState)
    
    # Register Nodes
    builder.add_node("guardrail", guardrail_node)
    builder.add_node("safety_fallback", safety_fallback_node)
    builder.add_node("analyzer", analyzer_node)
    builder.add_node("generator", content_generator_node)
    
    # Set Up Routing Workflow
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
    builder.add_edge("safety_fallback", END)
    builder.add_edge("generator", END)
    
    # Attach persistent local memory checkpointer
    memory_checkpointer = MemorySaver()
    return builder.compile(checkpointer=memory_checkpointer)

# Singleton compiled instance
bot_graph = create_compiled_graph()

# try:
#     with open("workflow_graph.png", "wb") as f:
#         f.write(bot_graph.get_graph().draw_mermaid_png())
#     print("Graph saved successfully as 'workflow_graph.png'")
# except Exception as e:
#     print(class_name := type(e).__name__, f": {e}")