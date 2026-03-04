from langchain.agents import AgentState
from typing import Annotated

def list_add_dicts(
    left: list[dict] | None = None, right: list[dict] | None = None
) -> list[dict]:
    """
    Add a new item to a list. No deduplication.
    Used for:
        * code: running the same code twice is meaningful;
    
    Added reset: if we pass an empty list, and left is not empty, it will return [].
    """
    if left is None:
        left = []
    if right is None:
        right = []

    if left is not None and len(right) == 0:
        return []

    return left + right


# NOTE: (!) CRUCIAL
# If we want to propagate the todos state var, added by the Middleware, to the general state,
# we need to still define the todos in state.
# If we try to pass the todos update to the general state, this will fail because the middleware
# automatically adds the state var only to the agent that has that middleware!

class MyState(AgentState):
    """
    Custom state for the graph. Inherits from AgentState -> automatically contains messages.

    Additional state variables:
        * code_logs (`list[dict[str, str]]`): 
            list of dicts containing input code and output+err logs;
        * todos (`list[dict]`): 
            list of todos for the analyst to perform. 
    """

    # ---- report features ----
    code_logs: Annotated[
        list[dict], list_add_dicts
    ]  # list of dicts (we need chronological order!), each dicts is input and output of a code block (out can be stdout or stderr or both)
    # ---- todos ----
    todos: list[dict]