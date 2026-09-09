from io import StringIO
import sys
from typing import Annotated
from langgraph.types import Command
from langchain_core.messages import ToolMessage
from langchain.tools import tool, ToolRuntime

_exec_globals: dict = {}

# helper
def python_executor(code: str) -> str:
    """Execute Python code locally and return stdout and stderr. State is preserved across calls."""
    stdout_capture = StringIO()
    stderr_capture = StringIO()

    old_stdout, old_stderr = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = stdout_capture, stderr_capture

    try:
        exec(code, _exec_globals, _exec_globals)  # globals == locals for persistent state
    except Exception as e:
        print(e, file=sys.stderr)
    finally:
        sys.stdout, sys.stderr = old_stdout, old_stderr

    stdout = stdout_capture.getvalue()
    stderr = stderr_capture.getvalue()

    return {
        "stdout" : stdout if stdout else "",
        "stderr" : stderr if stderr else ""
    }

# actual tool 
@tool 
async def execute_code(code: Annotated[str, "The Python code to execute"], runtime: ToolRuntime) -> Command:
    """
    Use this to execute python code. 
    """
    result = python_executor(code)

    return Command(
        update={
            "code_logs" : [result],
            "messages" : [ToolMessage(content=f"Code executed. \nstd out:\n```python\n{result['stdout']}\n```\n\nstd err:\n```python\n{result['stderr']}\n```", tool_call_id=runtime.tool_call_id)]
        }
    )
