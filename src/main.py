import asyncio
import uuid
from langchain_core.messages import HumanMessage
from graph.graph import get_checkpointer, make_graph


async def main() -> None:
    checkpointer, conn = await get_checkpointer()
    graph = make_graph(checkpointer=checkpointer)
    thread_id = str(uuid.uuid4())

    print("Epi Agent chat started.")
    print("Type /exit to quit.")

    try:
        while True:
            user_message = input("You: ").strip()
            if not user_message:
                continue

            if user_message == "/exit":
                print("Bye.")
                break

            config = {"configurable": {"thread_id": thread_id}}
            init_state = {"messages": [HumanMessage(content=user_message)]}

            try:
                result = await graph.ainvoke(init_state, config=config)
            except Exception as exc:
                print(f"Assistant error: {exc}")
                continue

            messages = result.get("messages", [])
            if not messages:
                print("AI: (no response)")
                continue

            ai_msg = messages[-1]
            ai_content = getattr(ai_msg, "content", "")
            print(f"AI: {ai_content}")
    finally:
        conn.close()


if __name__ == "__main__":
    asyncio.run(main())