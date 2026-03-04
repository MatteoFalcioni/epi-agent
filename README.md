# epi-agent
Agentic AI system with epidemiologic simulations capabilities 


## Roadmap

We will work on two branches of the project in parallel: 

1. The data analyst agent, which is specialized in analysing medical datasets 
2. The epidemiology agent, specialized on running simulations using epidemiologic models

### 1 - Data Analyst

My roadmap will be (may vary):

- create the graph in LangGraph: supervisor with two subagents (create prompts, state, graph, tools <- concept of tools initially). Supervisor will have structured output: next subagent + message. NOTE: maybe we do not need graph.PARENT with a supervisor node...? 

- we need conversational memory - you can use a simple asyncsqlite saver, locally

- define the tool for data analysis: python repl, can be done with sandbox or locally -> way easier to do it locally to work with data on our machine (no need for complete sandbox isolation)

- craft the most accurate prompt as possible for knowledge of the database

- enrich the data analyst agent with other tools to work on the dataset - ex: `get_field_description` to get the description of the columns at runtime (maybe not needed because of prompt? we'll check)

- craft the supervisor prompt for routing

#### Key Takes (reminders for myself)

Remember this does not need to be production ready, but more of a proof of concept. DO NOT overengineer it.