from typing import Annotated
from langchain.tools import tool, ToolRuntime
from langchain_core.messages import ToolMessage, HumanMessage
from langgraph.types import Command

def create_handoff_tool(
    *, agent_name: str, description: str | None = None
):  #  * means: from here on, all arguments must be passed as keyword arguments
    """
    Creates a handoff tool to transfer control to another agent. 
    The tool updates the messages with a tool message confirming the transfer and a human message containing the task to perform, 
    then issues a goto command to the target agent.
    """
    name = f"transfer_to_{agent_name}"
    description = description or f"Ask {agent_name} for help."

    # the actual handoff tool
    @tool(name, description=description)
    def handoff_tool(
        task: Annotated[str, "The task that the subagent should perform"],
        runtime: ToolRuntime,
    ) -> Command:

        tool_msg = ToolMessage(
            content=f"Successfully transferred to {agent_name}",
            tool_call_id=runtime.tool_call_id,
        )
        task_msg = HumanMessage(
            content=f"The agent supervisor advises you to perform the following task : \n{task}"
        )

        return Command(
            goto=agent_name,
            update={"messages": [tool_msg] + [task_msg]},
            graph=Command.PARENT,
        )

    return handoff_tool

assign_to_analyst = create_handoff_tool(agent_name="analyst")
assign_to_simulator = create_handoff_tool(agent_name="simulator")