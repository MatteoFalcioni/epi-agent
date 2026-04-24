import json
import sys


class Ansi:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BRIGHT_BLUE = "\033[94m"


# ── node → color mapping ──
_NODE_COLORS = {
    "supervisor": Ansi.CYAN,
    "agent_supervisor": Ansi.CYAN,
    "analyst": Ansi.GREEN,
    "analyst_agent": Ansi.GREEN,
    "simulator": Ansi.MAGENTA,
    "simulator_agent": Ansi.MAGENTA,
}


def _safe_json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)


def _w(text: str, color: str, pretty: bool) -> str:
    return f"{color}{text}{Ansi.RESET}" if pretty else text


class StreamPrinter:
    """Human-friendly, colored, streaming output for LangGraph events.

    Renders content_blocks from AIMessageChunk:
      • reasoning blocks   → dim, prefixed with 💭
      • text blocks        → node color
      • tool_call_chunk    → blue with 🔧
    Plus custom tool-IO events and node updates.
    """

    def __init__(self, pretty: bool = True) -> None:
        self.pretty = pretty
        self._current_node: str | None = None
        self._in_thinking = False
        self._in_tool_args = False

    # ── helpers ──────────────────────────────────────────────

    def _node_color(self, node_name: str) -> str:
        return _NODE_COLORS.get(node_name, Ansi.BLUE)

    def _ensure_node_header(self, node_name: str) -> None:
        if node_name == self._current_node:
            return
        self._close_open_sections()
        if self._current_node is not None:
            self._out("")
        color = self._node_color(node_name)
        self._out(_w(f"── {node_name} ──", f"{Ansi.BOLD}{color}", self.pretty))
        self._current_node = node_name

    def _close_open_sections(self) -> None:
        if self._in_thinking:
            self._out("")
            self._in_thinking = False
        if self._in_tool_args:
            self._out(_w(")", Ansi.BLUE, self.pretty))
            self._in_tool_args = False

    def _out(self, text: str = "", end: str = "\n") -> None:
        sys.stdout.write(text + end)
        sys.stdout.flush()

    # ── public API ───────────────────────────────────────────

    def print_banner(self) -> None:
        self._out(_w(
            "Epi Agent chat started. Type /exit to end conversation.",
            f"{Ansi.BOLD}{Ansi.CYAN}", self.pretty,
        ))

    def print_status(self, text: str) -> None:
        self._out(_w(text, Ansi.DIM, self.pretty))

    def print_error(self, text: str) -> None:
        self._out(_w(text, Ansi.RED, self.pretty))

    # ── main dispatch ────────────────────────────────────────

    def print_stream_event(self, stream_item) -> None:
        if not isinstance(stream_item, dict) or "type" not in stream_item:
            return

        event_type = stream_item["type"]
        data = stream_item.get("data")

        if event_type == "messages":
            self._handle_messages(data)
        elif event_type == "custom":
            self._handle_custom(data)
        elif event_type == "updates":
            self._handle_updates(data)
        # debug events are intentionally ignored (too noisy)

    # ── messages ─────────────────────────────────────────────

    def _handle_messages(self, data) -> None:
        if not isinstance(data, tuple) or len(data) != 2:
            return
        token, metadata = data
        node_name = (
            metadata.get("langgraph_node", "unknown")
            if isinstance(metadata, dict) else "unknown"
        )
        self._ensure_node_header(node_name)

        color = self._node_color(node_name)

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
                            self._out(
                                _w("💭 ", Ansi.DIM, self.pretty), end="",
                            )
                            self._in_thinking = True
                        self._out(_w(text, Ansi.DIM, self.pretty), end="")

                elif btype == "text":
                    text = block.get("text", "")
                    if text:
                        if self._in_thinking:
                            self._out("")
                            self._in_thinking = False
                        # Check for "Updated todo list" pattern and render nicely
                        if "Updated todo list to" in text:
                            import re
                            match = re.search(r"Updated todo list to (\[.*\])", text, re.DOTALL)
                            if match:
                                try:
                                    todos = json.loads(match.group(1))
                                    self._render_todos(todos)
                                    # Remove the raw text part
                                    remaining = text[:match.start()].strip()
                                    if remaining:
                                        self._out(_w(remaining, color, self.pretty), end="")
                                    continue
                                except json.JSONDecodeError:
                                    pass  # Fall through to regular text output
                        self._out(_w(text, color, self.pretty), end="")

                elif btype == "tool_call_chunk":
                    saw_tool_call_chunk = True
                    name = block.get("name")
                    args = block.get("args", "")
                    if name:
                        self._close_open_sections()
                        self._out(
                            _w(f"🔧 {name}(", Ansi.BLUE, self.pretty), end="",
                        )
                        self._in_tool_args = True
                    if args:
                        self._out(_w(args, Ansi.BLUE, self.pretty), end="")

        # ── 2. fallback: raw .content string (if no content_blocks) ──
        elif hasattr(token, "content") and token.content:
            content = token.content
            if isinstance(content, str) and content:
                if self._in_thinking:
                    self._out("")
                    self._in_thinking = False
                self._out(_w(content, color, self.pretty), end="")

        # ── 3. completed tool_calls — only if we didn't already show chunks ──
        if not saw_tool_call_chunk:
            tool_calls = getattr(token, "tool_calls", None)
            if tool_calls:
                self._close_open_sections()
                for tc in tool_calls:
                    name = tc.get("name", "?")
                    args = tc.get("args", {})
                    self._out(_w(
                        f"🔧 {name}({_safe_json(args)})", Ansi.BLUE, self.pretty,
                    ))

        # ── 4. done signal → close open sections ──
        resp_meta = getattr(token, "response_metadata", None) or {}
        if resp_meta.get("done"):
            self._close_open_sections()
            self._out("")  # blank line after response

    # ── custom: tool input / output events ───────────────────

    def _handle_custom(self, data) -> None:
        if not isinstance(data, dict):
            return
        event = data.get("event", "")
        tool_name = data.get("tool", "")

        if event == "tool_input":
            inputs = data.get("input", {})
            self._out(_w(
                f"  ⬇ {tool_name} input: {_safe_json(inputs)}",
                Ansi.BLUE, self.pretty,
            ))
        elif event == "tool_output":
            output = data.get("output", {})
            # Check if this is a todo list update and render it nicely
            if tool_name in ("update_todo_list", "TodoList") and isinstance(output, dict):
                if "todos" in output or "todo_list" in output:
                    todos = output.get("todos", output.get("todo_list", []))
                    self._render_todos(todos)
                    return
            self._out(_w(
                f"  ⬆ {tool_name} output: {_safe_json(output)}",
                Ansi.BRIGHT_BLUE, self.pretty,
            ))
        else:
            self._out(_w(
                f"  [custom] {_safe_json(data)}", Ansi.BRIGHT_BLUE, self.pretty,
            ))

    def _render_todos(self, todos: list) -> None:
        """Render a todo list with nice formatting."""
        if not todos:
            return
        
        # Box-drawing characters for the frame
        TOP_LEFT = "┌"
        TOP_RIGHT = "┐"
        BOTTOM_LEFT = "└"
        BOTTOM_RIGHT = "┘"
        HORIZONTAL = "─"
        VERTICAL = "│"
        
        # Status indicators with colors
        STATUS_COLORS = {
            "completed": Ansi.GREEN,
            "in_progress": Ansi.YELLOW,
            "pending": Ansi.DIM,
            "failed": Ansi.RED,
        }
        STATUS_SYMBOLS = {
            "completed": "✓",
            "in_progress": "▶",
            "pending": "○",
            "failed": "✗",
        }
        
        # Calculate max width for the box
        max_content_width = 0
        for todo in todos:
            content = todo.get("content", todo.get("text", str(todo)))
            max_content_width = max(max_content_width, len(content))
        
        # Header row
        header = " Todo List "
        box_width = max(max_content_width + 4, len(header) + 4)
        padding = box_width - len(header) - 2
        
        self._out(_w(
            f"  {TOP_LEFT}{HORIZONTAL * (box_width - 2)}{TOP_RIGHT}",
            Ansi.CYAN, self.pretty,
        ))
        self._out(_w(
            f"  {VERTICAL}{' ' * ((box_width - len(header) - padding) // 2)}{header}{' ' * ((box_width - len(header) + padding) // 2)}{VERTICAL}",
            Ansi.CYAN, self.pretty,
        ))
        self._out(_w(
            f"  {VERTICAL}{HORIZONTAL * (box_width - 2)}{VERTICAL}",
            Ansi.CYAN, self.pretty,
        ))
        
        # Todo items
        for todo in todos:
            content = todo.get("content", todo.get("text", str(todo)))
            status = todo.get("status", "pending")
            
            color = STATUS_COLORS.get(status, Ansi.DIM)
            symbol = STATUS_SYMBOLS.get(status, "○")
            
            # Truncate content if too long
            display_content = content[:max_content_width] if len(content) > max_content_width else content
            
            self._out(_w(
                f"  {VERTICAL} {symbol} {display_content}{' ' * (max_content_width - len(display_content))} {VERTICAL}",
                color, self.pretty,
            ))
        
        self._out(_w(
            f"  {BOTTOM_LEFT}{HORIZONTAL * (box_width - 2)}{BOTTOM_RIGHT}",
            Ansi.CYAN, self.pretty,
        ))

    # ── updates: node finished ───────────────────────────────

    def _handle_updates(self, data) -> None:
        if not isinstance(data, dict):
            return
        for node_name in data:
            color = self._node_color(node_name)
            self._out(_w(
                f"  ✓ {node_name} finished",
                f"{Ansi.DIM}{color}", self.pretty,
            ))
