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


# NOTE: (!) 
# If we want to propagate the variables added by middleware (todos) we need to add them to the state and update them in the nodes, 
# otherwise they will not be propagated in the graph and the middleware will not work properly. 
# Here I have a a doubt: is this necessary because supervisor has no node -> subagents are subgraphs,
# or is this generally needed? need to investigate...
# Also: we should be losing reducers for the middleware variables if we define state like we do below
# this isn't a problem for agents that do not work in parallel like in our case, but it surely isn't best practice

class MyState(AgentState):
    """
    Custom state for the graph. Inherits from AgentState -> automatically contains messages.

    Additional state variables:
        * code_logs (`list[dict[str, str]]`): 
            list of dicts containing input code and output+err logs;
        * todos (`list[dict]`): 
            list of todos for the analyst to perform. 
        * files (`dict`):
            dictionary of files managed by the filesystem middleware.
    """

    simulations: Annotated[
        list[dict], list_add_dicts
    ]  # list of dicts, each dicts is a simulation run with its datetime and results (parameters, metrics, etc.)
    code_logs: Annotated[
        list[dict], list_add_dicts
    ]  # list of dicts (we need chronological order!), each dicts is input and output of a code block (out can be stdout or stderr or both)
    # ---- variables added by middleware ----
    todos: list