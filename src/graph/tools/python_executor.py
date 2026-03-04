from langchain_core.tools import tool
from io import StringIO
import sys

_exec_globals: dict = {}

@tool
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

    return "\n".join(filter(None, [
        f"stdout:\n{stdout}" if stdout else "",
        f"stderr:\n{stderr}" if stderr else "",
    ])) or "(no output)"
