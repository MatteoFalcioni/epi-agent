from langgraph.types import Command
from typing_extensions import Literal
from langchain.agents import create_agent
from langgraph.graph import StateGraph, START
from langchain.agents.middleware import TodoListMiddleware
from langchain_core.messages import HumanMessage
from pydantic import SecretStr
from dotenv import load_dotenv
import os
import sqlite3
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from .utils import get_openrouter_model
from .state import MyState

from .prompts.analyst import PROMPT
from .prompts.supervisor import supervisor_prompt


load_dotenv()

async def get_checkpointer():
    """
    Initialize SQLite checkpointer once at app startup.
    Returns the checkpointer instance to be reused across all graph invocations.
    """
    conn = sqlite3.connect("checkpoints.db", check_same_thread=False)
    saver = AsyncSqliteSaver(conn)
    return saver, conn

def make_graph(
    checkpointer=None
):
    """
    Create a graph with custom config. Reuses the same checkpointer for all invocations.

    Args:
        checkpointer: Reused checkpointer instance from app startup.
    """

    # ======= API KEYS SETUP =======
    openrouter_api_key = SecretStr(os.getenv("OPENROUTER_API_KEY"))

    # ======= SUPERVISOR =======
    # use gpt-4.1 for supervisor (via OpenRouter)
    supervisor_llm = get_openrouter_model(
        model_name="openai/gpt-4.1",  
        api_key=openrouter_api_key
    ) 

    supervisor_agent = create_agent(
        model=supervisor_llm,
        tools=[],
        system_prompt=supervisor_prompt,
        name="agent_supervisor",
        state_schema=MyState
    )

    # ======= ANALYST AGENT =======

    # Create analyst LLM via OpenRouter
    llm = get_openrouter_model(
        model_name=os.getenv("ANALYST_MODEL", "openai/gpt-4.1"),  # default to gpt-4.1 if not set
        api_key=openrouter_api_key
    ) 

    tools = []

    analyst_agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=PROMPT,  # System prompt for the analyst agent
        name="analyst_agent",
        state_schema=MyState,
        middleware=[
            TodoListMiddleware()
        ],
    )

    # -------ANALYST AGENT NODE-------
    async def analyst_agent_node(
        state: MyState,
    ) -> Command[Literal["supervisor"]]:
        """
        Main node of the graph.
        """
        print("[GRAPH] Entering analyst_agent_node")
        # invoke the agent
        result = await analyst_agent.ainvoke(state)

        last_msg = result["messages"][-1]
        code_logs = result.get("code_logs", [])

        # update and route back
        # NOTE: if you do not update todos here, the todos are not generally updated! 
        todos = result.get("todos", [])

        return Command(
            update={
                "messages": HumanMessage(content=last_msg.content),  # update messages with the last message content
                "code_logs" : code_logs,
                "todos": todos,  # propagate the todos
            },
            goto="supervisor",
        )

    # -------SIMULATOR AGENT NODE-------
    async def simulator_agent_node(
        state: MyState,
    ) -> Command[Literal["supervisor"]]:
        """
        Simulator node. For now, it just routes back to the supervisor.
        """
        print("[GRAPH] Entering simulator_agent_node")
        # Here you would implement the logic for the simulator agent, similar to the analyst agent.
        # For now, we just route back to the supervisor.

        return Command(
            update={},  # you can add updates here as needed
            goto="supervisor",
        )
    

    # ======= GRAPH  BUILDING =======

    builder = StateGraph(MyState)
        
    builder.add_node(
        "supervisor", supervisor_agent
    )  # , destinations=("data_analyst", "simulator", END)
    builder.add_node("data_analyst", analyst_agent_node)
    builder.add_node("simulator", simulator_agent_node)
    builder.add_edge(
        START, "supervisor"
    )  # since we have Command(goto=...) everywhere, we do not need other edges.

    graph = builder.compile(checkpointer=checkpointer)

    return graph