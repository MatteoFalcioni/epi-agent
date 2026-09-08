import asyncio
import token
import uuid
import os   
from langchain_core.messages import HumanMessage
from graph.graph import get_checkpointer, make_graph
import matplotlib

import json
import markdown
import time

from pathlib import Path


os.environ["GRADIO_ANALYTICS_ENABLED"] = "false"
os.environ["HF_HUB_OFFLINE"] = "1" 


import gradio as gr

from cli.streaming_gui import StreamPrinter



matplotlib.use('Agg')  

    


#-------Init--------------------------------------------------------------------------
IMAGES_DIR = Path("agent_outputs").resolve()
IMAGES_DIR.mkdir(exist_ok=True)


messager = StreamPrinter()

async def init_system():
    checkpointer, conn = await get_checkpointer()
    graph = make_graph(checkpointer=checkpointer)
    thread_id = str(uuid.uuid4())
    return graph, conn, {"configurable": {"thread_id": thread_id}}



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
                yield f"<p>⚠️  Inner Error: {inner_e}</p>"


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
        yield f"<p>⚠️ Outer Error: {outer_e}</p>"





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
            gr.Image("assets/epidemia_logo.png", show_label=False)

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
                    "assets/epidemia_chat.png",
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