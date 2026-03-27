import asyncio
import uuid
from langchain_core.messages import HumanMessage
from graph.graph import get_checkpointer, make_graph
from cli.streaming import StreamPrinter


async def main() -> None:
    checkpointer, conn = await get_checkpointer()
    graph = make_graph(checkpointer=checkpointer)
    thread_id = str(uuid.uuid4())
    printer = StreamPrinter(pretty=True)

    printer.print_banner()

    try:
        while True:
            try:
                user_message = input("You> ").strip()
            except EOFError:
                print("\nBye.")
                break
            if not user_message:
                continue

            if user_message == "/exit":
                print("Bye.")
                break

            config = {"configurable": {"thread_id": thread_id}}
            init_state = {"messages": [HumanMessage(content=user_message)]}

            try:
                async for chunk in graph.astream(
                    init_state,
                    config=config,
                    stream_mode=["messages", "updates", "custom"],
                    version="v2",
                    subgraphs=True,
                ):
                    printer.print_stream_event(chunk)

                print()  # ensure final newline
            except Exception as exc:
                printer.print_error(f"Error: {exc}")
                continue
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())