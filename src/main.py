import asyncio
import uuid
from langchain_core.messages import HumanMessage
from rich.console import Console
from rich.prompt import Prompt
from graph.graph import get_checkpointer, make_graph


console = Console()


def _extract_text_from_chunk(content) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)
    return ""


async def main() -> None:
    checkpointer, conn = await get_checkpointer()
    graph = make_graph(checkpointer=checkpointer)
    thread_id = str(uuid.uuid4())

    console.print("[bold cyan]Epi Agent chat started. Type /exit to end conversation.[/bold cyan]")
    console.print("[dim]Type /exit to quit.[/dim]")

    try:
        while True:
            user_message = Prompt.ask("[bold green]You[/bold green]").strip()
            if not user_message:
                continue

            if user_message == "/exit":
                console.print("[bold cyan]Bye.[/bold cyan]")
                break

            config = {"configurable": {"thread_id": thread_id}}
            init_state = {"messages": [HumanMessage(content=user_message)]}

            try:
                console.print("[bold blue]AI[/bold blue]: ", end="")
                current_node = None
                printed_anything = False

                async for chunk in graph.astream(
                    init_state,
                    config=config,
                    stream_mode=["messages", "updates"],
                    version="v2",
                ):
                    chunk_type = chunk.get("type")

                    if chunk_type == "messages":
                        message_chunk, metadata = chunk["data"]
                        node_name = metadata.get("langgraph_node", "unknown")
                        text = _extract_text_from_chunk(getattr(message_chunk, "content", None))

                        if not text:
                            continue

                        if node_name != current_node:
                            if printed_anything:
                                console.print()
                            console.print(f"[dim][{node_name}][/dim] ", end="")
                            current_node = node_name

                        console.print(text, end="")
                        printed_anything = True

                console.print()
            except Exception as exc:
                console.print(f"[bold red]Assistant error:[/bold red] {exc}")
                continue
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())