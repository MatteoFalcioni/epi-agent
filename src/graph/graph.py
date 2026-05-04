from langgraph.types import Command
from typing_extensions import Literal
from langchain.agents import create_agent
from langgraph.graph import StateGraph, START
from langchain.agents.middleware import TodoListMiddleware
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from dotenv import load_dotenv
import os
import aiosqlite

from .utils import get_ollama_model
from .state import MyState
from .tools.handoffs import assign_to_analyst, assign_to_simulator
from .tools.python_executor import execute_code
from .tools.simulator import (
    fit_gammasir_from_csv,
    fit_seir_from_csv,
    fit_sir_from_csv,
    compute_incidence,
)
from .prompts.analyst import analyst_prompt
from .prompts.supervisor import supervisor_prompt
#from .prompts.simulator import simulator_prompt


load_dotenv()

async def get_checkpointer():
    """
    Initialize SQLite checkpointer once at app startup.
    Returns the checkpointer instance to be reused across all graph invocations.
    """
    conn = await aiosqlite.connect("checkpoints.db")
    saver = AsyncSqliteSaver(conn)
    return saver, conn

def make_graph(
    checkpointer=None
):
    """
    Creates the graph. Reuses the same checkpointer for all invocations if provided.

    Args:
        checkpointer: Reused checkpointer instance.
    """

    # ======= SUPERVISOR =======
    supervisor_llm = get_ollama_model(
        model_name=os.getenv("SUPERVISOR_MODEL", "qwen3.5:27b"),  # default to qwen3.5:27b if not set
    ) 

    supervisor_agent = create_agent(
        model=supervisor_llm,
        tools=[assign_to_analyst, assign_to_simulator],
        system_prompt=supervisor_prompt,
        name="agent_supervisor",
        state_schema=MyState
    )

    # ======= ANALYST AGENT =======
    llm = get_ollama_model(
        model_name=os.getenv("ANALYST_MODEL", "qwen3.5:27b"),  # default to qwen3.5:27b if not set
        temperature=0.0
    ) 

    tools = [execute_code, fit_sir_from_csv, fit_seir_from_csv, fit_gammasir_from_csv, compute_incidence]  # Analyst can also run simulations if needed

    analyst_agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=analyst_prompt,  # System prompt for the analyst agent
        name="analyst_agent",
        state_schema=MyState,
        middleware=[
            TodoListMiddleware()
        ],
    )

    '''# ======= SIMULATOR AGENT =======
    simulator_llm = get_ollama_model(
        model_name=os.getenv("SIMULATOR_MODEL", "qwen3.5:27b"),  # default to qwen3.5:27b if not set
        temperature=0.0
    )

    simulator_agent = create_agent(
        model=simulator_llm,
        tools=[fit_sir_from_csv, fit_seir_from_csv, fit_gammasir_from_csv, compute_incidence],
        system_prompt=simulator_prompt,
        name="simulator_agent",
        state_schema=MyState,
        middleware=[TodoListMiddleware()],  # Simulator has access to filesystem as well
    )'''

    # ======= NODES =======
    # -------ANALYST AGENT NODE-------
    def analyst_agent_node(
        state: MyState,
    ) -> Command[Literal["supervisor"]]:
        """
        Main node of the graph.
        """
        print("[GRAPH] Entering analyst_agent_node")
        # invoke the agent
        result = analyst_agent.invoke(state["messages"])

        # get results
        last_msg = result["messages"][-1]
        code_logs = result.get("code_logs", [])
        todos = result.get("todos", [])
        files = result.get("files", [])  # also updating filesytem middleware if there are any file updates

        # Propagate subagent's updates in the general state and route back to the supervisor for the next iteration.
        # NOTE: if you do not update todos here, the todos are not generally updated! 
        return Command(
            update={
                "messages": [HumanMessage(content=last_msg.content)],  # update messages with the last message content
                "code_logs" : code_logs,
                "todos": todos,  # propagate the todos
                "files": files,  # propagate file updates to the filesystem middleware
            },
            goto="supervisor",
        )

    '''# -------SIMULATOR AGENT NODE-------
    def simulator_agent_node(
        state: MyState,
    ) -> Command[Literal["supervisor"]]:
        """
        Simulator node.
        """
        print("[GRAPH] Entering simulator_agent_node")

        result = simulator_agent.invoke(state)
        last_msg = result["messages"][-1]
        files = result.get("files", []) # simulator has filessytem as well 

        return Command(
            update={
                "messages": [HumanMessage(content=last_msg.content)],
                "files": files,  
            },
            goto="supervisor",
        )'''
    
    # ======= GRAPH  BUILDING =======

    builder = StateGraph(MyState)
        
    builder.add_node(
        "supervisor", supervisor_agent
    )  # , destinations=("data_analyst", "simulator", END)
    builder.add_node("analyst", analyst_agent_node)
    #builder.add_node("simulator", simulator_agent_node)
    builder.add_edge(
        START, "supervisor"
    )  # since we have Command(goto=...) everywhere, we do not need other edges.

    graph = builder.compile(checkpointer=checkpointer)

    return graph