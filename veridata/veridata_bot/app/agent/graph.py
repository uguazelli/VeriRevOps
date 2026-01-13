from langgraph.graph import END, START, StateGraph

from app.agent.nodes import human_handoff_node, rag_node, router_node
from app.agent.state import AgentState


# ==================================================================================
# CONDITIONAL EDGE LOGIC (The Router's Brain)
# ==================================================================================
def route_decision(state: AgentState):
    """Called AFTER the 'router' node.
    It checks the 'intent' field stored in the state (RAG vs HUMAN)
    and tells the graph which node to visit next.
    """
    intent = state.get("intent")
    if intent == "human":
        # If user wants a human, go to Handoff Node
        return "human_handoff"
    else:
        # Defaults to RAG (even for small talk, which is RAG with complexity=1)
        return "rag"


# ==================================================================================
# BUILD THE GRAPH (The Workflow Definition)
# ==================================================================================
def build_graph():
    """Compiles and returns the LangGraph executable."""
    workflow = StateGraph(AgentState)

    # ------------------------------------------------------------------
    # 1. ADD NODES (The Workers)
    # ------------------------------------------------------------------
    # 'router': First step. Uses LLM to classify intent.
    workflow.add_node("router", router_node)

    # 'human_handoff': If user wants human, this node crafts the handover message.
    workflow.add_node("human_handoff", human_handoff_node)

    # 'rag': The main workhorse. Calls vector DB to answer questions.
    workflow.add_node("rag", rag_node)

    # ------------------------------------------------------------------
    # 2. DEFINES EDGES (The Connections)
    # ------------------------------------------------------------------
    # Start -> Router
    workflow.add_edge(START, "router")

    # Router -> (Conditional) -> Handoff OR RAG
    workflow.add_conditional_edges("router", route_decision, {"human_handoff": "human_handoff", "rag": "rag"})

    # ------------------------------------------------------------------
    # 3. DEFINE EXITS
    # ------------------------------------------------------------------
    # Both paths lead to the End (Exit)
    workflow.add_edge("human_handoff", END)
    workflow.add_edge("rag", END)

    return workflow.compile()


# Global instance for import
agent_app = build_graph()
