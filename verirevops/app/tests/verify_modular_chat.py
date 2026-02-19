import asyncio
from app.orchestration.chat import build_chat_graph
from app.core.logger import Log

async def verify_graph():
    try:
        Log.info("Attempting to compile chat graph...")
        graph = build_chat_graph()
        Log.success("Chat graph compiled successfully!")

        # Print nodes for visual verification
        print("\nCompiled Nodes:")
        for node_name in graph.nodes:
            print(f" - {node_name}")

    except Exception as e:
        Log.error(f"Failed to compile chat graph: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(verify_graph())
