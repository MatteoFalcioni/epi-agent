import asyncio
import token
import uuid
import os   
from langchain_core.messages import HumanMessage
from graph.graph import get_checkpointer, make_graph
import matplotlib

import re
import json
import sys
import markdown
import time

from pathlib import Path


os.environ["GRADIO_ANALYTICS_ENABLED"] = "false"
os.environ["HF_HUB_OFFLINE"] = "1" 

import gradio as gr


matplotlib.use('Agg')  


def is_html(text: str) -> bool:
    return bool(re.search(r'<[a-zA-Z][^>]*>', text))


def _safe_json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)


class StreamPrinter:
    """Human-friendly, colored, streaming output for LangGraph events.

    Renders content_blocks from AIMessageChunk:
      • reasoning blocks   → dim, prefixed with 💭
      • text blocks        → node color
      • tool_call_chunk    → blue with 🔧
    Plus custom tool-IO events and node updates.
    """

    def __init__(self) -> None:
        self._current_node: str | None = None
        self._in_thinking = False
        self._in_tool_args = False

    # ── helpers ──────────────────────────────────────────────




    def _close_open_sections(self) -> None:
        if self._in_thinking:
            self._in_thinking = False
        if self._in_tool_args:
            self._in_tool_args = False





    # ── main dispatch ────────────────────────────────────────

    def print_stream_event(self, stream_item) -> None:
        if not isinstance(stream_item, dict) or "type" not in stream_item:
            return 'reasoning', ''

        event_type = stream_item["type"]
        data = stream_item.get("data")

        if event_type == "messages":
            return self._handle_messages(data)
        elif event_type == "custom":
            return self._handle_custom(data)
        elif event_type == "updates":
            return self._handle_updates(data)
        # debug events are intentionally ignored (too noisy)

    # ── messages ─────────────────────────────────────────────

    def _handle_messages(self, data) -> None:
        if not isinstance(data, tuple) or len(data) != 2:
            return 'reasoning', ''
        token, metadata = data
        node_name = (
            metadata.get("langgraph_node", "unknown")
            if isinstance(metadata, dict) else "unknown"
        )

        if getattr(token, "type", "") == "tool":
            tool_name = getattr(token, "name", "")

            if tool_name == "execute_code":
                return 'reasoning', f"\n\n💻 **Python script Output:**\n{token.content}\n"

        # ── 1. content_blocks (preferred, works for Ollama + Anthropic + OpenAI) ──
        content_blocks = getattr(token, "content_blocks", None)
        saw_tool_call_chunk = False

        if content_blocks:
            for block in content_blocks:
                if not isinstance(block, dict):
                    continue
                btype = block.get("type")

                if btype == "reasoning":
                    text = block.get("reasoning", "")
                    if text:
                        if not self._in_thinking:
                            self._close_open_sections()
                        return btype, text

                elif btype == "text":
                    text = block.get("text", "")
                    if text:
                        if self._in_thinking:
                            self._in_thinking = False

                        return btype, text

                elif btype == "tool_call_chunk":
                    saw_tool_call_chunk = True
                    name = block.get("name")
                    args = block.get("args", "")
                    if name:
                        self._close_open_sections()
                        self._in_tool_args = True
                    if args:
                        return 'reasoning', f'🔧 {name} ({args})'

        # ── 2. fallback: raw .content string (if no content_blocks) ──
        elif hasattr(token, "content") and token.content:
            content = token.content
            if isinstance(content, str) and content:
                if self._in_thinking:
                   
                    self._in_thinking = False
            return 'reasoning', content

        # ── 3. completed tool_calls — only if we didn't already show chunks ──
        if not saw_tool_call_chunk:
            tool_calls = getattr(token, "tool_calls", None)
            if tool_calls:
                self._close_open_sections()
                for tc in tool_calls:
                    name = tc.get("name", "?")
                    args = tc.get("args", {})
                    return 'reasoning', f"🔧 {name}({_safe_json(args)})"
            return 'reasoning', ' '

        # ── 4. done signal → close open sections ──
        resp_meta = getattr(token, "response_metadata", None) or {}
        if resp_meta.get("done"):
            self._close_open_sections()
            return 'reasoning',' '
        

    
    def _handle_custom(self, data) -> None:
        if not isinstance(data, dict):
            return
        event = data.get("event", "")
        tool_name = data.get("tool", "")

        if event == "tool_input":
            inputs = data.get("input", {})
            return 'reasoning', f"  ⬇ {tool_name} input: {_safe_json(inputs)}"
        elif event == "tool_output":
            output = data.get("output", {})
            # Check if this is a todo list update and render it nicely
            # The write_todos tool from TodoListMiddleware outputs "Updated todo list to [...]" in the ToolMessage
            if tool_name == "write_todos" and isinstance(output, str):
                return 'reasoning', output
            
                # Parse the todo list from the "Updated todo list to [...]" message
                '''import re
                match = re.search(r"Updated todo list to (\[.*\])", output, re.DOTALL)
                if match:
                    try:
                        todos = json.loads(match.group(1))
                        self._render_todos(todos)
                        return 'reasoning', 
                    except json.JSONDecodeError:
                        pass  # Fall through to regular output'''
            return 'reasoning', f"  ⬆ {tool_name} output: {_safe_json(output)}"
        else:
            return 'reasoning', f"  [custom] {_safe_json(data)}"
        

    def _handle_updates(self, data) -> None:
        if not isinstance(data, dict):
            return
        for node_name in data:
            return 'reasoning', f"  ✓ {node_name} finished \n\n"

    
    



#-------Init--------------------------------------------------------------------------
IMAGES_DIR = Path("agent_outputs").resolve()
IMAGES_DIR.mkdir(exist_ok=True)


messager = StreamPrinter()

async def init_system():
    checkpointer, conn = await get_checkpointer()
    graph = make_graph(checkpointer=checkpointer)
    thread_id = str(uuid.uuid4())
    return graph, conn, {"configurable": {"thread_id": thread_id}}

#graph, conn, config = asyncio.run(init_system())


system_initialized = False
graph = None
config = None
conn = None

async def chat(message, history):
    global system_initialized, graph, config, conn
    
    if not system_initialized:
        g, c, cfg = await init_system()
        graph = g
        conn = c
        config = cfg
        system_initialized = True

    init_state = {"messages": [HumanMessage(content=message)]}
    response_text = ""
    thinking_text = ""

    try:
        async for chunk in graph.astream(
            init_state,
            config=config,
            stream_mode=["messages", "updates", "custom"],
            version="v2",
            subgraphs=True,
        ):
            
            try:
                result = messager.print_stream_event(chunk)

                if result is None:
                    continue  # skip if the event was not recognized or had no content
                
                data = chunk.get('data')

                if isinstance(data, tuple) and len(data) == 2:
                    token, metadata = data
                    node_name = (
                        metadata.get("langgraph_node", "unknown")
                        if isinstance(metadata, dict) else "unknown"
                    )

                type_token, token = result 
                if token:
                    if node_name in ['analyst', 'analyst_agent', 'analyst_agent_node']:
                        thinking_text += token
                        thinking_html = markdown.markdown(thinking_text, extensions=['fenced_code', 'tables'])

                    else:
                        if type_token == 'reasoning':
                            thinking_text += token
                            thinking_html = markdown.markdown(thinking_text, extensions=['fenced_code', 'tables'])
                        elif type_token == 'text':
                            response_text += token
                            response_html = markdown.markdown(response_text, extensions=['fenced_code', 'tables'])

                    if thinking_text and response_text:
                        full = f"<details open><summary>💭 Thinking...</summary>" + f"<small>{thinking_html}</small></details>" + f"\n\n{response_html}"
                    elif thinking_text:
                        full = f"<details open><summary>💭 Thinking...</summary>" + f"<small>{thinking_html}</small></details>"
                    else:
                        full = f"\n\n{response_text}"
                    yield full

                    await asyncio.sleep(0)
                
            except asyncio.CancelledError:
                raise

            except BaseException as inner_e:
                import traceback
                print(f"!!! INNER ERROR: {inner_e}")
                print(traceback.format_exc())
                yield f"<p>⚠️ Errore interno: {inner_e}</p>"


        thinking_html = markdown.markdown(thinking_text, extensions=['fenced_code', 'tables'])
        response_html = markdown.markdown(response_text, extensions=['fenced_code', 'tables'])

        # Final state
        if thinking_text and response_text:
            final_output = f"<details><summary>💭 Thinking</summary><small>{thinking_html}</small></details>\n\n{response_html}"
        elif thinking_text:
            final_output = f"<details><summary>💭 Thinking Completato</summary><small>{thinking_html}</small></details>"
        else:
            final_output = response_html

        yield final_output
            


    except asyncio.CancelledError:
        # Gradio cancella il task, qui puoi fare cleanup
        return
    
    except BaseException as outer_e:
        import traceback
        print(f"!!! OUTER ERROR: {outer_e}")
        print(traceback.format_exc())
        yield f"<p>⚠️ Errore: {outer_e}</p>"





# --- UI -----------------------------------------------------------------------------------
seen_images = set()


START_TIME = time.time()

def refresh_gallery():
    files = list(IMAGES_DIR.glob("*.png")) + list(IMAGES_DIR.glob("*.jpg"))
    session_files = [f for f in files if f.stat().st_mtime >= START_TIME]
    return [str(f) for f in sorted(session_files, key=lambda f: f.stat().st_mtime)]




toggle_dark_mode = """
function() {
    document.querySelector('body').classList.toggle('dark');
}
"""



with gr.Blocks(title="Epidem-IA", theme=gr.themes.Glass()) as demo:
    with gr.Row():
        with gr.Column(scale=8):
            gr.Markdown("<h1 style='text-align: center; margin-bottom: 0;'> 🧬 Epidem-IA Dashboard 🧬</h1>")
        
        
        theme_btn = gr.Button("🌓 Theme", variant="secondary", size="sm", scale=1, min_width=100)
    
    theme_btn.click(None, None, None, js=toggle_dark_mode)
    gr.Markdown("---")

    #gr.Markdown("<h1 style='text-align: center; margin-bottom: 0;'> Chat with Epidem-IA epidemiological agent 🦠🧪🔬💉🧬🩺  and see its thoughts 💭 </h1>")
    

    with gr.Row():
        with gr.Column(scale=1):
            gr.Image("epidemia_logo2.png", show_label=False)

            gallery = gr.Gallery(
                label="📊 Images produced",
                columns=2,
                height="auto",
                show_label=True,
            )
            timer = gr.Timer(2)
            timer.tick(refresh_gallery, outputs=[gallery])


        with gr.Column(scale=3):
            chatbot = gr.Chatbot(
                label="Epidem-IA",
                avatar_images=(
                    None,
                    "epidemia_chat_png.png",
                ),
                height=600
            )
            gr.ChatInterface(
                fn=chat,
                #title="🧬 Epidem-IA",
                chatbot=chatbot,
                textbox=gr.Textbox(
                    placeholder="Write a message...",
                    lines=1,
                    scale=10,
                    submit_btn="⬆️ Send",
                    stop_btn='⏹️ Stop'
                )
            )




if __name__ == "__main__":
    demo.launch(server_port=2223, share = False)