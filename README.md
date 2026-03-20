# epi-agent
Agentic AI system with epidemiologic simulations & data-analysis capabilities 

## Quick Start 

### 1. 📥 Clone & Install

*Recommended: create a conda environment or a python venv first, for complete isolation*

Then:

```bash
git clone https://github.com/MatteoFalcioni/epi-agent
cd epi-agent
pip install -r requirements.txt
```

### 2. 🔧 Configure Environment
Create `.env` from template:
```bash
cp .env.template .env
# Edit .env with your API keys and configuration
```

Required variables:

- `OPENROUTER_API_KEY` - needed for llm api calls

Optional Variables:

LangSmith variables to trace agent's runs (useful for dewbugging)

- `LANGSMITH_TRACING`
- `LANGSMITH_ENDPOINT`
- `LANGSMITH_API_KEY`
- `LANGSMITH_PROJECT`

Set them up quickly [here](https://smith.langchain.com/o/2b3dff8d-ea0b-44a3-a981-4377843f21c8). Learn more about Langsmith traces [here](https://docs.langchain.com/langsmith/create-account-api-key#create-an-account-and-api-key).

### 3. Run the agent

```bash

python src/main.py

```

---


## Roadmap

We will work on two branches of the project in parallel: 

1. The data analyst agent, which is specialized in analysing medical datasets 
2. The epidemiology agent, specialized on running simulations using epidemiologic models

### 1 - Data Analyst

My roadmap will be (may vary):

- create the graph in LangGraph: supervisor with two subagents (create prompts, state, graph, tools <- concept of tools initially). Supervisor will have structured output: next subagent + message. NOTE: maybe we do not need graph.PARENT with a supervisor node...? DONE

- we need conversational memory - you can use a simple asyncsqlite saver, locally. DONE

- define the tool for data analysis: python repl, can be done with sandbox or locally -> way easier to do it locally to work with data on our machine (no need for complete sandbox isolation) DONE

- craft the most accurate prompt as possible for knowledge of the database

- enrich the data analyst agent with other tools to work on the dataset - ex: `get_field_description` to get the description of the columns at runtime (maybe not needed because of prompt? we'll check)

- craft the supervisor prompt for routing

#### Key Takes (reminders for myself)

Remember this does not need to be production ready, but more of a proof of concept. DO NOT overengineer it.