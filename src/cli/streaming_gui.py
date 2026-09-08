import json


def _safe_json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)




class StreamPrinter:
    """Human-friendly, colored, streaming output for LangGraph events.

    Renders content_blocks from AIMessageChunk:
      • reasoning blocks   → dim, prefixed with 💭
      • text blocks        → normal
      • tool_call_chunk    → with 🔧
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

            if tool_name:
                return 'reasoning', f"\n\n🔧 **{tool_name} Output:**\n{token.content}\n"

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
    
            return 'reasoning', f"  ⬆ {tool_name} output: {_safe_json(output)}"
        else:
            return 'reasoning', f"  [custom] {_safe_json(data)}"
        

    def _handle_updates(self, data) -> None:
        if not isinstance(data, dict):
            return
        for node_name in data:
            return 'reasoning', f"  ✓ {node_name} finished \n\n"
